"""对一个接口做压测：同时假装成 N 个用户不停打它，输出 QPS 和延迟分布。

先读 src/evidence_desk/perf/stats.py 的注释了解统计口径，这里只负责「发请求」。

怎么用（务必按这个顺序，别一上来就压花钱的接口）：

1) 先压不调大模型的接口，测你自己框架的天花板（免费，可以随便压）：
     uv run python scripts/load_test.py --url http://127.0.0.1:8000/ready \\
         --concurrency 1,10,50,100 --requests 100

2) 再小规模压真实链路，看真实数字（每个请求都会真的调模型，会花钱）：
     uv run python scripts/load_test.py --url http://127.0.0.1:8000/api/v1/agent/chat \\
         --json '{"question": "如何启用调试日志？"}' \\
         --concurrency 1,5 --requests 10

为什么分两步：第二步的数字里混着中转站的限速和排队，那是**别人系统**的能力。
先用第一步把「你的代码能扛多少」单独测出来，两个数一对比，才知道瓶颈在哪边。
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from evidence_desk.perf.stats import (
    LoadReport,
    RequestOutcome,
    format_table,
    summarize,
)


class _Progress:
    """跑的过程中打个进度，别让人对着一行「跑并发 N …」干瞪眼。

    压测天然会慢（等模型几秒是正常的），所以「慢」和「卡死」长得一模一样。
    没有进度输出的话，唯一的区分办法是干等到超时——这正是第一版的毛病。
    """

    def __init__(self, total: int) -> None:
        self._total = total
        self._done = 0
        # 每完成 10% 打一次，不刷屏也不至于长时间没动静。
        self._step = max(1, total // 10)

    def tick(self, outcome: RequestOutcome) -> None:
        self._done += 1
        if self._done % self._step and self._done != self._total:
            return
        mark = (
            ""
            if outcome.ok
            else f"（最近一个失败：{outcome.error or outcome.status_code}）"
        )
        print(f"  {self._done}/{self._total} {mark}", flush=True)


async def _one_request(
    client: httpx.AsyncClient,
    *,
    url: str,
    payload: dict[str, Any] | None,
    semaphore: asyncio.Semaphore,
    progress: _Progress | None = None,
) -> RequestOutcome:
    """发一个请求，记下耗时和结局。

    semaphore 是「并发闸门」：最多同时放 N 个进去，第 N+1 个要等前面有人出来。
    这就是「并发数」的实现——没有它，几百个请求会一瞬间全发出去，
    压的是你本机的网络栈，不是服务端的处理能力。

    这里刻意不抛异常：一个请求超时是**压测结果的一部分**（说明服务顶不住了），
    不是脚本出错。抛出去会把整轮压测打断，那就什么数据都拿不到了。
    """
    async with semaphore:
        started_at = perf_counter()
        try:
            if payload is None:
                response = await client.get(url)
            else:
                response = await client.post(url, json=payload)
            outcome = RequestOutcome(
                elapsed_ms=(perf_counter() - started_at) * 1000,
                status_code=response.status_code,
            )
        except httpx.TimeoutException:
            outcome = RequestOutcome(
                elapsed_ms=(perf_counter() - started_at) * 1000,
                status_code=None,
                error="timeout",
            )
        except httpx.HTTPError as exc:
            outcome = RequestOutcome(
                elapsed_ms=(perf_counter() - started_at) * 1000,
                status_code=None,
                error=type(exc).__name__,
            )

    if progress:
        progress.tick(outcome)
    return outcome


async def preflight(
    url: str, payload: dict[str, Any] | None, timeout: float
) -> str | None:
    """正式开压前先打一个请求探路，有问题就返回一句人话说明。

    为什么必须有这一步：压测的请求本来就慢，所以「服务没起」「服务卡在启动」
    和「服务就是慢」在屏幕上长得一样——都是没动静。不探路的话，一个起不来的
    服务会让你白等「请求数 × 超时秒数」那么久（200 × 60 秒 = 三个多小时）。

    探路用很短的超时，因为这一步只关心「能不能通」，不关心「快不快」。
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if payload is None:
                response = await client.get(url)
            else:
                response = await client.post(url, json=payload)
        if not 200 <= response.status_code < 300:
            # 第一版只看「连得上吗」，结果接口每次都 500 也照样放行，
            # 白打了 20 个必失败的请求。能连上 ≠ 能用。
            body = response.text[:300].replace("\n", " ")
            return (
                f"接口返回 {response.status_code}，不是成功响应。先修好再压测。\n"
                f"  响应体：{body}\n"
                f"  真正的报错堆栈在服务端日志里（uvicorn 那个终端）"
            )
    except httpx.ConnectError:
        return (
            "连不上：服务没起，或者端口不对。先跑 uv run uvicorn evidence_desk.main:app"
        )
    except httpx.TimeoutException:
        return (
            f"连上了但 {timeout:.0f} 秒内不回话：服务多半卡在启动阶段"
            "（要连 Postgres/Weaviate，先确认 docker compose up -d 起来了）"
        )
    except httpx.HTTPError as exc:
        return f"请求失败：{type(exc).__name__}"
    return None


async def run_round(
    *,
    url: str,
    payloads: list[dict[str, Any] | None],
    concurrency: int,
    total_requests: int,
    timeout_seconds: float,
    payload_offset: int = 0,
) -> LoadReport:
    """跑一轮：固定并发数，打满 total_requests 个请求。

    payload_offset：从第几个请求体开始取。多档并发连着跑时必须往后顺延——
    否则第二档又从第一个问题开始，而那些问题刚被第一档问过，直接命中缓存，
    第二档测出来的就全是假数字。

    请求体不够用时会绕回头复用，绕回去的部分同样会吃缓存。
    """
    semaphore = asyncio.Semaphore(concurrency)
    # 连接池上限要 >= 并发数，否则请求会卡在「等一个空闲连接」上，
    # 测出来的延迟里混进了客户端自己的排队时间。
    limits = httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=concurrency
    )
    progress = _Progress(total_requests)

    async with httpx.AsyncClient(timeout=timeout_seconds, limits=limits) as client:
        started_at = perf_counter()
        outcomes = await asyncio.gather(
            *(
                _one_request(
                    client,
                    url=url,
                    payload=payloads[(payload_offset + i) % len(payloads)],
                    semaphore=semaphore,
                    progress=progress,
                )
                for i in range(total_requests)
            )
        )
        wall_seconds = perf_counter() - started_at

    return summarize(list(outcomes), concurrency=concurrency, wall_seconds=wall_seconds)


def _load_payloads(
    raw: str | None, path: str | None = None
) -> list[dict[str, Any] | None]:
    """解析请求体：--json 传一个（或一组），--json-file 从文件读一组。

    为什么要支持「一组」：这个项目的 Agent 挂了响应缓存中间件，同一个问题问
    第二次会直接吃缓存、不调模型。拿同一个请求体压 10 次，第 1 个是真调用、
    后 9 个是查字典——测出来的 QPS 是缓存的 QPS，跟系统真实容量没关系。
    要量真实容量，每个请求都得是「没问过的问题」。

    注意缓存是**进程内**的（一个 OrderedDict，见 response_cache_middleware.py），
    所以重启服务就清空了。同一组问题想再压一次，重启 uvicorn 即可。
    """
    if path is not None:
        parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    elif raw is not None:
        parsed = json.loads(raw)
    else:
        return [None]

    if isinstance(parsed, list):
        if not parsed:
            raise ValueError("请求体列表是空的")
        return list(parsed)
    return [parsed]


async def _main_async(args: argparse.Namespace) -> None:
    payloads = _load_payloads(args.json, args.json_file)
    concurrencies = [int(c) for c in args.concurrency.split(",")]

    print(f"目标：{'POST' if payloads[0] else 'GET'} {args.url}")
    print(f"每轮请求数：{args.requests}，超时：{args.timeout}s")
    if payloads[0] is not None:
        print(f"请求体个数：{len(payloads)}", end="")
        if len(payloads) < args.requests:
            # 请求体不够就得循环复用，重复的那些会命中响应缓存，把 QPS 抬虚高。
            print(f"（少于请求数 {args.requests}，重复部分会吃缓存，数字会偏乐观）")
        else:
            print()
    print()

    preflight_timeout = (
        args.timeout if args.preflight_timeout is None else args.preflight_timeout
    )
    print(f"探路中（最多等 {preflight_timeout:.0f} 秒）…", flush=True)
    problem = await preflight(args.url, payloads[0], preflight_timeout)
    if problem:
        print(f"✗ {problem}", file=sys.stderr)
        sys.exit(2)
    print("✓ 接口可达，开始压测\n")

    reports = []
    # 探路已经用掉了第 0 个请求体（它是一次真实请求，也进了缓存），所以从 1 开始。
    payload_offset = 1 if payloads[0] is not None else 0
    for concurrency in concurrencies:
        print(f"跑并发 {concurrency} …", flush=True)
        report = await run_round(
            url=args.url,
            payloads=payloads,
            concurrency=concurrency,
            total_requests=args.requests,
            timeout_seconds=args.timeout,
            payload_offset=payload_offset,
        )
        payload_offset += args.requests
        reports.append(report)

    if payloads[0] is not None and payload_offset > len(payloads):
        print(
            f"\n⚠ 这次一共要 {payload_offset} 个不重复的问题，"
            f"但文件里只有 {len(payloads)} 个——超出的部分绕回头复用了，"
            "那些请求会命中缓存，数字偏乐观。"
            "\n  要么减少请求数，要么往问题文件里多加几条，"
            "要么重启服务清空缓存后分几次跑。",
            file=sys.stderr,
        )

    print()
    print(format_table(reports))


def main() -> None:
    parser = argparse.ArgumentParser(description="接口压测")
    parser.add_argument("--url", required=True, help="要压的完整 URL")
    parser.add_argument(
        "--json",
        default=None,
        help="POST 请求体（JSON 字符串；也可以是一个数组，轮流用）。不传就发 GET",
    )
    parser.add_argument(
        "--json-file",
        default=None,
        help=(
            "从文件读一组请求体（JSON 数组），比在命令行里塞一长串好使。"
            "现成的：data/evaluation/load_test_questions.json"
        ),
    )
    parser.add_argument(
        "--concurrency",
        default="1,10,50",
        help="并发数，逗号分隔，依次跑。看的是拐点出现在哪一档",
    )
    parser.add_argument("--requests", type=int, default=100, help="每轮发多少个请求")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="单个请求超时秒数。调 LLM 的接口要给够，否则满屏 timeout",
    )
    parser.add_argument(
        "--preflight-timeout",
        type=float,
        default=None,
        help=(
            "探路请求的超时秒数。默认跟 --timeout 一样——"
            "探路本身就是一个正常请求，接口慢它也得慢，"
            "给短了会把「接口本来就要等这么久」误判成「服务卡住了」"
        ),
    )
    args = parser.parse_args()

    try:
        asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
