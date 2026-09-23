"""把一堆「每个请求花了多久、成没成功」汇总成一份压测结论。

纯函数，不发请求、不碰网络——发请求在 scripts/load_test.py 里。
这样百分位这种最容易算错的地方能用普通列表直接测。
"""

from collections import Counter
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class RequestOutcome:
    """一个请求的结局。"""

    elapsed_ms: float
    # HTTP 状态码；连接失败/超时这类根本没拿到响应的，记 None。
    status_code: int | None
    # 失败原因（超时、连接被拒…），成功时是 None。
    error: str | None = None

    @property
    def ok(self) -> bool:
        """2xx 才算成功。5xx 是服务顶不住了，4xx 是请求本身有问题，都算失败。"""
        return self.status_code is not None and 200 <= self.status_code < 300


@dataclass(frozen=True)
class LoadReport:
    """一轮压测的结论。"""

    concurrency: int
    total_requests: int
    succeeded: int
    # 整轮从第一个请求发出到最后一个结束的墙上时间，算 QPS 的分母。
    wall_seconds: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    # 失败原因 → 次数，例如 {"timeout": 3, "http_500": 1}。
    failures: dict[str, int]

    @property
    def failed(self) -> int:
        return self.total_requests - self.succeeded

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.succeeded / self.total_requests

    @property
    def qps(self) -> float:
        """每秒完成多少个请求。墙上时间为 0 时返回 0，避免除零。"""
        if self.wall_seconds <= 0:
            return 0.0
        return self.total_requests / self.wall_seconds


def percentile(values: list[float], pct: float) -> float:
    """取第 pct 百分位（0~100），用最近秩法（nearest-rank）。

    做法：排序后取第 ceil(pct/100 × n) 个（从 1 数起）。
    p95 = 100 个里的第 95 个 = 「95% 的请求不慢于这个数」。

    为什么不取平均值：95 个 1 秒 + 5 个 30 秒，平均 2.45 秒看着还行，
    但有 5 个用户等了半分钟——平均值会把长尾藏起来，百分位不会。

    为什么用最近秩而不是插值：插值会造出一个「谁都没经历过」的数字
    （比如 3.7 秒，但实际只有 3.2 和 4.1 两个请求）。压测报告要的是
    真实发生过的耗时，不是数学上的平滑值。
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    # max(1, ...) 兜住 pct=0 的情况：排名至少是第 1 个，不能是第 0 个。
    rank = max(1, ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _failure_key(outcome: RequestOutcome) -> str:
    """给失败归个类，便于一眼看出是超时还是服务报错。"""
    if outcome.error:
        return outcome.error
    return f"http_{outcome.status_code}"


def summarize(
    outcomes: list[RequestOutcome], *, concurrency: int, wall_seconds: float
) -> LoadReport:
    """把一轮的所有请求结局汇总成报告。

    百分位只用成功请求算。混进失败的会污染结论：一个 50 毫秒就被拒的请求
    会把 P95 拉低，看上去「更快了」，其实是更早挂了。
    """
    succeeded = [o for o in outcomes if o.ok]
    latencies = [o.elapsed_ms for o in succeeded]
    failures = Counter(_failure_key(o) for o in outcomes if not o.ok)

    return LoadReport(
        concurrency=concurrency,
        total_requests=len(outcomes),
        succeeded=len(succeeded),
        wall_seconds=wall_seconds,
        p50_ms=percentile(latencies, 50),
        p90_ms=percentile(latencies, 90),
        p95_ms=percentile(latencies, 95),
        p99_ms=percentile(latencies, 99),
        max_ms=max(latencies) if latencies else 0.0,
        failures=dict(failures),
    )


def format_table(reports: list[LoadReport]) -> str:
    """把几轮不同并发的结果排成一张表，看拐点在哪。"""
    header = (
        f"{'并发':>6}{'请求数':>8}{'QPS':>9}{'成功率':>9}"
        f"{'P50(ms)':>10}{'P95(ms)':>10}{'P99(ms)':>10}{'最慢(ms)':>11}"
    )
    lines = [header, "-" * len(header)]
    for r in reports:
        lines.append(
            f"{r.concurrency:>6}{r.total_requests:>8}{r.qps:>9.2f}"
            f"{r.success_rate:>8.1%}"
            f"{r.p50_ms:>10.1f}{r.p95_ms:>10.1f}{r.p99_ms:>10.1f}{r.max_ms:>11.1f}"
        )
    failing = [r for r in reports if r.failures]
    if failing:
        lines.append("")
        lines.append("失败明细：")
        for r in failing:
            detail = "、".join(f"{k}×{v}" for k, v in sorted(r.failures.items()))
            lines.append(f"  并发 {r.concurrency}：{detail}")
    return "\n".join(lines)
