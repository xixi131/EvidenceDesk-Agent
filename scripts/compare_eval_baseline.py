"""把最新的评测结果跟基线比一遍，打印对比表；有指标退步就以非 0 退出。

这个退出码是「评测」和「CI」之间唯一的那根线：CI 不看你打印了什么，只看
退出码——0 是绿，非 0 是红。

用法：
    uv run python scripts/compare_eval_baseline.py retrieval
    uv run python scripts/compare_eval_baseline.py            # 三份基线全比
    uv run python scripts/compare_eval_baseline.py answer --update   # 认可新分数

退出码：
    0  全部在容差内
    1  有指标退步超出容差
    2  文件缺失 / 基线里的路径在结果文件里找不到（工程错误，不是质量退步）

跟其他 run_*_eval.py 的分工：那些脚本负责「跑出分数」，这个脚本只负责
「拿分数跟尺子比」。它不跑模型、不连数据库，所以又快又免费，CI 里可以随便跑。
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from evidence_desk.evaluation.baseline import (
    MetricPathError,
    compare,
    format_report,
    parse_baseline,
    refreshed_baseline_data,
)

BASELINE_DIR = Path("data/evaluation/baselines")
# 比较顺序按「系统的层次」排：检索是地基，地基塌了上面全白搭，所以先看它。
DEFAULT_EVALS = ["retrieval", "answer", "agent"]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_commit() -> str:
    """取当前 commit 的短 sha，用于 --update 时记录「这个基线是哪次代码的产物」。"""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def _compare_one(eval_name: str, *, update: bool) -> int:
    """比一份基线，返回这一份的退出码。"""
    baseline_path = BASELINE_DIR / f"{eval_name}.json"
    if not baseline_path.exists():
        print(f"✗ 找不到基线文件：{baseline_path}", file=sys.stderr)
        return 2

    baseline_data = _load_json(baseline_path)
    result_path = Path(baseline_data["result_path"])
    if not result_path.exists():
        # 典型原因：还没跑过这个评测。这是工程问题不是质量问题，用 2 区分开。
        print(
            f"✗ 找不到结果文件：{result_path}（先跑对应的 run_*_eval.py）",
            file=sys.stderr,
        )
        return 2

    result = _load_json(result_path)

    try:
        report = compare(parse_baseline(baseline_data), result)
    except MetricPathError as exc:
        print(f"✗ {eval_name}：{exc}", file=sys.stderr)
        return 2

    print(format_report(report))

    if update:
        refreshed = refreshed_baseline_data(
            baseline_data,
            result,
            approved_at=date.today().isoformat(),
            approved_commit=_current_commit(),
        )
        baseline_path.write_text(
            json.dumps(refreshed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n✓ 已把 {baseline_path} 更新为本次结果（这是你在签字认可新分数）")
        return 0

    return 1 if report.has_regression else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="评测结果 vs 基线对比")
    # 这里不能用 choices=DEFAULT_EVALS：nargs="*" 会拿「一个都没传」的空列表
    # 去撞 choices，导致不带参数跑直接报 invalid choice。改成手动校验。
    parser.add_argument(
        "evals",
        nargs="*",
        help=f"要比哪几份基线（{'/'.join(DEFAULT_EVALS)}），默认全比",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="把基线更新成本次结果。必须由人显式触发——自动写回等于没有基线",
    )
    args = parser.parse_args()

    eval_names = args.evals or DEFAULT_EVALS
    unknown = [name for name in eval_names if name not in DEFAULT_EVALS]
    if unknown:
        parser.error(
            f"未知的评测名：{'、'.join(unknown)}（可选：{'/'.join(DEFAULT_EVALS)}）"
        )
    if args.update and len(eval_names) != 1:
        parser.error("--update 一次只能更新一份基线，请明确指定，例如：answer --update")

    exit_codes = []
    for i, name in enumerate(eval_names):
        if i:
            print("\n" + "=" * 72 + "\n")
        exit_codes.append(_compare_one(name, update=args.update))

    # 取最严重的那个：2（工程错误）> 1（质量退步）> 0。
    sys.exit(max(exit_codes))


if __name__ == "__main__":
    main()
