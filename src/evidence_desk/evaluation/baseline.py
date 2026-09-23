"""评测基线：存一把尺子，用来判断「这次跑出来的分数，比上次认可的差了没有」。

跟 metrics.py / agent_metrics.py 是同一个约定：纯函数 + 不可变数据类，不碰 IO；
读写文件、算 git sha 这些都放在 scripts/compare_eval_baseline.py 里，
所以这里的每个函数都能用普通字典直接测，不用准备磁盘文件。

为什么需要「基线」这个东西：评测跑出来的是分数不是对错，一个 0.89 单独看没有
意义，必须跟「上一次被认可的分数」比才知道是涨是跌。而那个被认可的分数必须
存成文件——存在脑子里机器读不到，CI 就没法自动判断。这个文件就是基线。

它跟 data/evaluation/*.json 那些结果文件的区别只有一条：
    结果文件   每跑一次评测就被覆盖    = 这次考了多少分
    基线文件   只有人手动改才会变      = 说好的及格线是多少
必须是两个文件，因为一个会变、一个不能变。

一份基线（data/evaluation/baselines/*.json）里有三块：
    result_path   跑完评测之后，新分数去哪个文件里读
    config        这个分数是在什么配置下得到的（配置变了，分数就没有可比性）
    metrics       每个指标：去哪读、上次多少、越大越好还是越小越好、允许抖多少
"""

from dataclasses import dataclass
from typing import Any, Literal

# 指标的方向。大部分指标越大越好（Recall、准确率），但有一类是越小越好
# （过度拒答率、未经审批的写操作率）。不区分方向的话，over_refusal_rate
# 从 0.07 涨到 0.15 会被当成「进步」，正好判反。
Direction = Literal["higher_is_better", "lower_is_better"]

# 单个指标的判定结果。
Status = Literal["ok", "improved", "regressed"]

# 浮点比较的宽容量。指标都是四位小数，1e-9 远小于任何真实差异，
# 只用来吃掉 0.90-0.85=0.050000000000000044 这类表示误差。
_FLOAT_EPS = 1e-9


@dataclass(frozen=True)
class MetricBaseline:
    """基线里的一个指标：一把尺子的一个刻度。"""

    name: str
    # 去结果文件里的哪个位置读这个数，点号分层，例如 "methods.Hybrid.recall@5"。
    # 存路径而不是直接写死取法，是因为三个评测脚本的输出结构各不一样，
    # 有了这个字段，一个比较器就能同时伺候检索/回答/Agent 三种报告。
    path: str
    value: float
    direction: Direction
    # 允许的抖动幅度。绝对值，不是百分比——原因见 _drop 的注释。
    tolerance: float


@dataclass(frozen=True)
class Baseline:
    """一份完整的基线。"""

    eval_name: str
    result_path: str
    dataset_version: str
    approved_at: str
    approved_commit: str
    note: str
    # 配置指纹：key 是结果文件里的点号路径，value 是当初跑出这个分数时的取值。
    config: dict[str, Any]
    metrics: list[MetricBaseline]


@dataclass(frozen=True)
class MetricComparison:
    """一个指标比完之后的结论。"""

    name: str
    baseline_value: float
    current_value: float
    # 「变差了多少」。正数 = 退步，负数 = 进步。方向的差异在这里已经被抹平，
    # 所以后面判定只认这一个数，不用再关心 higher/lower is better。
    drop: float
    tolerance: float
    status: Status


@dataclass(frozen=True)
class ConfigDrift:
    """配置指纹对不上：这次跑的配置跟基线当初的配置不一样。"""

    key: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ComparisonReport:
    """整份报告：配置有没有漂，哪些指标退步了。"""

    eval_name: str
    baseline: Baseline
    comparisons: list[MetricComparison]
    drifts: list[ConfigDrift]

    @property
    def has_regression(self) -> bool:
        """只要有一个指标退步超出容差，整份报告就算红。"""
        return any(c.status == "regressed" for c in self.comparisons)


class MetricPathError(KeyError):
    """结果文件里找不到基线指定的那条路径。"""


def read_path(data: dict[str, Any], path: str) -> Any:
    """按点号路径从嵌套字典里取值，例如 "methods.Hybrid.recall@5"。

    取不到就抛 MetricPathError，并且把完整路径带上——排查时能一眼看出是
    哪一段断的，比 Python 原生的 KeyError('Hybrid') 有用得多。

    注意：JSON 的 key 永远是字符串，所以 avg_recall 里的 K 值写成 "avg_recall.5"
    而不是整数 5，这里不用做类型转换。
    """
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise MetricPathError(f"结果文件里找不到路径：{path}（断在 {part!r}）")
        current = current[part]
    return current


def read_metric(data: dict[str, Any], path: str) -> float:
    """按路径读一个指标值，并确认它真的是个数。"""
    value = read_path(data, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricPathError(f"路径 {path} 取到的不是数字：{value!r}")
    return float(value)


def _drop(metric: MetricBaseline, current: float) -> float:
    """算「变差了多少」，把两种方向统一成同一个符号约定。

    容差用绝对值差而不是百分比变化，是因为这里的指标基本都是 0~1 的比率。
    对 write_without_approval_rate 这种基线为 0 的指标，百分比根本算不出来
    （除以 0）；对 0.05 这种小分母，涨 0.01 就是 20%，用百分比会天天误报。
    """
    if metric.direction == "higher_is_better":
        return metric.value - current
    return current - metric.value


def compare_metric(metric: MetricBaseline, current: float) -> MetricComparison:
    """把一个指标的当前值跟基线比出 ok / improved / regressed。

    容差是双向的：退步没超过容差算 ok，进步没超过容差也算 ok（噪音而已，
    别急着庆祝）。只有超出容差的变化才值得标出来。

    比较时加了 _FLOAT_EPS：0.90 - 0.85 在浮点数里是 0.050000000000000044，
    直接跟容差 0.05 比会判成退步。正好掉到容差线上的情况天天有（指标本来就是
    1/48、1/16 这种分数），不处理的话会稳定误报。
    """
    drop = _drop(metric, current)
    if drop - metric.tolerance > _FLOAT_EPS:
        status: Status = "regressed"
    elif -drop - metric.tolerance > _FLOAT_EPS:
        status = "improved"
    else:
        status = "ok"
    return MetricComparison(
        name=metric.name,
        baseline_value=metric.value,
        current_value=current,
        drop=drop,
        tolerance=metric.tolerance,
        status=status,
    )


def compare_config(baseline: Baseline, result: dict[str, Any]) -> list[ConfigDrift]:
    """核对配置指纹，返回所有对不上的项。

    对不上不代表出错——你可能就是故意在做实验（换模型、调 top_k）。但它意味着
    「这次的分数和基线不是同一个条件下的产物」，比较结果只能当参考。所以这里
    只负责找出来，判红判绿不归它管（见 ComparisonReport.has_regression）。
    """
    drifts = []
    for key, expected in baseline.config.items():
        try:
            actual = read_path(result, key)
        except MetricPathError:
            actual = None
        if actual != expected:
            drifts.append(ConfigDrift(key=key, expected=expected, actual=actual))
    return drifts


def compare(baseline: Baseline, result: dict[str, Any]) -> ComparisonReport:
    """拿一份基线和一份新结果，产出完整对比报告。"""
    return ComparisonReport(
        eval_name=baseline.eval_name,
        baseline=baseline,
        comparisons=[
            compare_metric(metric, read_metric(result, metric.path))
            for metric in baseline.metrics
        ],
        drifts=compare_config(baseline, result),
    )


def parse_baseline(data: dict[str, Any]) -> Baseline:
    """把基线 JSON 解析成 Baseline（文件读取在 scripts 层，这里只管解析）。"""
    return Baseline(
        eval_name=data["eval"],
        result_path=data["result_path"],
        dataset_version=data["dataset_version"],
        approved_at=data["approved_at"],
        approved_commit=data["approved_commit"],
        note=data["note"],
        config=data["config"],
        metrics=[
            MetricBaseline(
                name=name,
                path=spec["path"],
                value=float(spec["value"]),
                direction=spec["direction"],
                tolerance=float(spec["tolerance"]),
            )
            for name, spec in data["metrics"].items()
        ],
    )


def refreshed_baseline_data(
    data: dict[str, Any],
    result: dict[str, Any],
    *,
    approved_at: str,
    approved_commit: str,
) -> dict[str, Any]:
    """按当前结果刷新基线内容，用于「签字认可新分数」。

    只动会变的部分（各指标的 value、配置指纹的取值、认可时间和 commit），
    path / direction / tolerance / note 这些是人定的，原样保留。

    这个动作必须由人显式触发（compare_eval_baseline.py --update），不能让
    评测脚本跑完自动写回去——那样基线就变成了「最近一次结果」，
    永远跟当前代码一致，也就永远发现不了退步。
    """
    refreshed = dict(data)
    refreshed["approved_at"] = approved_at
    refreshed["approved_commit"] = approved_commit
    refreshed["config"] = {key: read_path(result, key) for key in data["config"]}
    refreshed["metrics"] = {
        name: {**spec, "value": read_metric(result, spec["path"])}
        for name, spec in data["metrics"].items()
    }
    return refreshed


def format_report(report: ComparisonReport) -> str:
    """把报告渲染成一张给人看的表（CI 日志和本地终端共用同一份输出）。"""
    baseline = report.baseline
    lines = [
        f"评测：{report.eval_name}",
        f"基线：{baseline.approved_at} @ {baseline.approved_commit}"
        f"（{baseline.dataset_version}）",
        f"说明：{baseline.note}",
        "",
    ]

    if report.drifts:
        lines.append("⚠ 配置指纹对不上，下面的对比只能当参考：")
        for drift in report.drifts:
            lines.append(
                f"  {drift.key}：基线 {drift.expected!r} → 本次 {drift.actual!r}"
            )
        lines.append("")

    header = f"{'指标':<32}{'基线':>10}{'本次':>10}{'变化':>10}{'容差':>8}  判定"
    lines.append(header)
    lines.append("-" * len(header))
    marks = {"ok": "—", "improved": "↑ 变好", "regressed": "↓ 退步"}
    for c in report.comparisons:
        # 展示用「变化」= 本次 - 基线，跟人的直觉一致（负数就是数字变小了）；
        # 判定用的是 drop（已抹平方向），两者不一定同号，这是有意的。
        change = c.current_value - c.baseline_value
        lines.append(
            f"{c.name:<32}{c.baseline_value:>10.4f}{c.current_value:>10.4f}"
            f"{change:>+10.4f}{c.tolerance:>8.4f}  {marks[c.status]}"
        )

    lines.append("")
    if report.has_regression:
        bad = [c.name for c in report.comparisons if c.status == "regressed"]
        lines.append(f"结论：退步 {len(bad)} 项 → {'、'.join(bad)}")
    else:
        lines.append("结论：没有指标退步超出容差")
    return "\n".join(lines)
