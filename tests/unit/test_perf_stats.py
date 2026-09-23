"""压测统计口径的单元测试（不发任何请求）。"""

from evidence_desk.perf.stats import RequestOutcome, percentile, summarize


def _ok(elapsed_ms: float) -> RequestOutcome:
    return RequestOutcome(elapsed_ms=elapsed_ms, status_code=200)


# --- 百分位 -----------------------------------------------------------------


def test_p95_picks_a_real_observed_value() -> None:
    # 1~100 共 100 个：第 95 个就是 95.0，不做插值、不造中间值。
    values = [float(n) for n in range(1, 101)]
    assert percentile(values, 95) == 95.0
    assert percentile(values, 50) == 50.0
    assert percentile(values, 99) == 99.0


def test_percentile_hides_nothing_that_the_mean_would_hide() -> None:
    # 95 个 1000ms + 5 个 30000ms：平均 2450ms「看着还行」，
    # 但 P99 会把那条 30 秒的长尾抖出来。
    values = [1000.0] * 95 + [30000.0] * 5
    assert percentile(values, 95) == 1000.0
    assert percentile(values, 99) == 30000.0


def test_percentile_of_empty_is_zero_not_a_crash() -> None:
    # 一轮全失败时延迟列表是空的，报告仍然要打得出来。
    assert percentile([], 95) == 0.0


def test_percentile_handles_single_value() -> None:
    assert percentile([42.0], 95) == 42.0


def test_percentile_zero_does_not_underflow_to_rank_zero() -> None:
    assert percentile([5.0, 9.0], 0) == 5.0


# --- 汇总 -------------------------------------------------------------------


def test_qps_is_requests_over_wall_time() -> None:
    report = summarize([_ok(100.0)] * 20, concurrency=10, wall_seconds=4.0)
    assert report.qps == 5.0
    assert report.success_rate == 1.0


def test_qps_is_zero_when_wall_time_is_zero() -> None:
    report = summarize([_ok(1.0)], concurrency=1, wall_seconds=0.0)
    assert report.qps == 0.0


def test_failures_are_grouped_by_reason() -> None:
    outcomes = [
        _ok(100.0),
        RequestOutcome(elapsed_ms=60000.0, status_code=None, error="timeout"),
        RequestOutcome(elapsed_ms=60000.0, status_code=None, error="timeout"),
        RequestOutcome(elapsed_ms=50.0, status_code=500),
    ]
    report = summarize(outcomes, concurrency=4, wall_seconds=1.0)

    assert report.succeeded == 1
    assert report.failed == 3
    assert report.failures == {"timeout": 2, "http_500": 1}


def test_percentiles_ignore_failed_requests() -> None:
    # 那条 50ms 就被拒的 500，不能把 P95 拉低成「更快了」。
    outcomes = [_ok(1000.0)] * 9 + [RequestOutcome(elapsed_ms=50.0, status_code=500)]
    report = summarize(outcomes, concurrency=10, wall_seconds=1.0)

    assert report.p95_ms == 1000.0
    assert report.max_ms == 1000.0


def test_4xx_counts_as_failure() -> None:
    report = summarize(
        [RequestOutcome(elapsed_ms=10.0, status_code=422)],
        concurrency=1,
        wall_seconds=1.0,
    )
    assert report.succeeded == 0
    assert report.failures == {"http_422": 1}
