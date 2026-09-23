"""评测基线对比逻辑的单元测试（纯字典进、纯结论出，不碰磁盘和网络）。"""

import pytest

from evidence_desk.evaluation.baseline import (
    Baseline,
    MetricBaseline,
    MetricPathError,
    compare,
    compare_metric,
    parse_baseline,
    read_metric,
    read_path,
    refreshed_baseline_data,
)


def _metric(
    *,
    value: float = 0.9,
    direction: str = "higher_is_better",
    tolerance: float = 0.05,
) -> MetricBaseline:
    return MetricBaseline(
        name="m",
        path="m",
        value=value,
        direction=direction,  # type: ignore[arg-type]
        tolerance=tolerance,
    )


# --- 路径读取 ---------------------------------------------------------------


def test_read_path_walks_nested_dicts() -> None:
    data = {"methods": {"Hybrid": {"recall@5": 0.9608}}}
    assert read_path(data, "methods.Hybrid.recall@5") == 0.9608


def test_read_path_handles_numeric_string_keys() -> None:
    # JSON 的 key 永远是字符串，retrieval 报告里的 K 值就是 "5" 而不是 5。
    assert read_metric({"avg_recall": {"5": 0.9314}}, "avg_recall.5") == 0.9314


def test_read_path_reports_full_path_when_missing() -> None:
    with pytest.raises(MetricPathError) as exc:
        read_path({"methods": {"Dense": {}}}, "methods.Hybrid.recall@5")
    # 报错要带上完整路径和断点，否则排查时只能看到一个光秃秃的 'Hybrid'。
    assert "methods.Hybrid.recall@5" in str(exc.value)
    assert "Hybrid" in str(exc.value)


def test_read_metric_rejects_non_numeric() -> None:
    with pytest.raises(MetricPathError):
        read_metric({"answer_model": "gpt-5.5"}, "answer_model")


def test_read_metric_rejects_bool() -> None:
    # Python 里 True 也是 int，不特判的话 bool 会被当成 1.0 混进指标。
    with pytest.raises(MetricPathError):
        read_metric({"ok": True}, "ok")


# --- 单指标判定 -------------------------------------------------------------


def test_higher_is_better_regresses_when_drop_exceeds_tolerance() -> None:
    result = compare_metric(_metric(value=0.90, tolerance=0.05), 0.84)
    assert result.status == "regressed"
    assert result.drop == pytest.approx(0.06)


def test_higher_is_better_tolerates_small_drop() -> None:
    assert compare_metric(_metric(value=0.90, tolerance=0.05), 0.86).status == "ok"


def test_drop_exactly_at_tolerance_is_still_ok() -> None:
    # 边界取「严格大于才算退步」，不然容差 0.05 会把正好掉 0.05 判红。
    assert compare_metric(_metric(value=0.90, tolerance=0.05), 0.85).status == "ok"


def test_big_gain_is_marked_improved() -> None:
    assert (
        compare_metric(_metric(value=0.90, tolerance=0.05), 0.97).status == "improved"
    )


def test_lower_is_better_flips_the_direction() -> None:
    metric = _metric(value=0.08, direction="lower_is_better", tolerance=0.05)
    # 过度拒答率涨上去 = 退步，不是进步。
    assert compare_metric(metric, 0.20).status == "regressed"
    assert compare_metric(metric, 0.01).status == "improved"


def test_zero_tolerance_metric_reds_on_any_regression() -> None:
    # 安全类指标（未经审批的写操作）发生一次都不算噪音。
    metric = _metric(value=0.0, direction="lower_is_better", tolerance=0.0)
    assert compare_metric(metric, 0.0).status == "ok"
    assert compare_metric(metric, 0.0625).status == "regressed"


# --- 整份报告 ---------------------------------------------------------------


def _baseline(metrics: list[MetricBaseline], config: dict | None = None) -> Baseline:
    return Baseline(
        eval_name="agent",
        result_path="data/evaluation/agent_eval_v1.json",
        dataset_version="v1",
        approved_at="2026-09-23",
        approved_commit="be52f73",
        note="测试用",
        config=config or {},
        metrics=metrics,
    )


def test_report_is_red_if_any_single_metric_regressed() -> None:
    baseline = _baseline(
        [
            MetricBaseline("good", "a", 0.9, "higher_is_better", 0.05),
            MetricBaseline("bad", "b", 0.9, "higher_is_better", 0.05),
        ]
    )
    report = compare(baseline, {"a": 0.95, "b": 0.70})
    assert report.has_regression is True


def test_report_is_green_when_everything_within_tolerance() -> None:
    baseline = _baseline([MetricBaseline("m", "a", 0.9, "higher_is_better", 0.05)])
    assert compare(baseline, {"a": 0.88}).has_regression is False


def test_config_drift_is_reported_but_does_not_turn_the_report_red() -> None:
    # 配置变了往往是你故意在做实验，所以只提醒、不判红——但必须让人看见，
    # 否则会拿一把量 Dense 的尺子去量 Hybrid 的系统。
    baseline = _baseline(
        [MetricBaseline("m", "a", 0.9, "higher_is_better", 0.05)],
        config={"top_k": 5},
    )
    report = compare(baseline, {"a": 0.9, "top_k": 8})
    assert report.has_regression is False
    assert [(d.key, d.expected, d.actual) for d in report.drifts] == [("top_k", 5, 8)]


def test_missing_config_key_counts_as_drift() -> None:
    baseline = _baseline([], config={"prompt_version": "answer-v1"})
    assert compare(baseline, {}).drifts[0].actual is None


# --- 解析与刷新 -------------------------------------------------------------


_RAW_BASELINE = {
    "eval": "agent",
    "result_path": "data/evaluation/agent_eval_v1.json",
    "dataset_version": "v1",
    "approved_at": "2026-09-01",
    "approved_commit": "old1234",
    "note": "首轮基线",
    "config": {"num_cases": 16},
    "metrics": {
        "task_success_rate": {
            "path": "task_success_rate",
            "value": 0.9,
            "direction": "higher_is_better",
            "tolerance": 0.07,
        }
    },
}


def test_parse_baseline_reads_the_file_shape() -> None:
    baseline = parse_baseline(_RAW_BASELINE)
    assert baseline.eval_name == "agent"
    assert baseline.metrics[0].name == "task_success_rate"
    assert baseline.metrics[0].tolerance == 0.07


def test_refresh_updates_values_and_signature_only() -> None:
    result = {"num_cases": 20, "task_success_rate": 1.0}
    refreshed = refreshed_baseline_data(
        _RAW_BASELINE, result, approved_at="2026-09-23", approved_commit="be52f73"
    )
    assert refreshed["metrics"]["task_success_rate"]["value"] == 1.0
    assert refreshed["config"]["num_cases"] == 20
    assert refreshed["approved_at"] == "2026-09-23"
    assert refreshed["approved_commit"] == "be52f73"
    # 人定的东西原样保留：容差、方向、路径、说明都不会被自动改掉。
    assert refreshed["metrics"]["task_success_rate"]["tolerance"] == 0.07
    assert refreshed["metrics"]["task_success_rate"]["direction"] == "higher_is_better"
    assert refreshed["note"] == "首轮基线"


def test_refresh_does_not_mutate_the_original() -> None:
    refreshed = refreshed_baseline_data(
        _RAW_BASELINE,
        {"num_cases": 20, "task_success_rate": 1.0},
        approved_at="2026-09-23",
        approved_commit="be52f73",
    )
    assert _RAW_BASELINE["approved_commit"] == "old1234"
    assert refreshed is not _RAW_BASELINE
