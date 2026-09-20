"""标识符抽取与保留率指标的单元测试（P6-02）。

这套指标是 P6-02 结论的依据，如果抽取规则本身有漏，报告里的"保留率 1.0"
就是假的。所以这里把正例、反例、边界都钉死。
"""

from evidence_desk.evaluation.query_rewrite_metrics import (
    diff_identifiers,
    extract_identifiers,
    summarize_identifiers,
)


def test_extracts_common_github_actions_identifiers() -> None:
    """项目里真实出现的四类标识符都要能抽出来。"""

    text = (
        "如何启用 ACTIONS_STEP_DEBUG，用 workflow_dispatch 触发 "
        "actions/checkout@v4，并用 fromJSON 解析？"
    )

    assert extract_identifiers(text) == [
        "ACTIONS_STEP_DEBUG",
        "workflow_dispatch",
        "actions/checkout@v4",
        "fromJSON",
    ]


def test_ignores_generic_words() -> None:
    """GitHub / JSON 这类通用词不算精确标识符。

    它们在几乎每条问题里都出现、也永远不会被改写丢掉，算进保留率
    只会往分母里塞必然得分的项，把真实丢失率稀释掉。
    """

    assert extract_identifiers("GitHub Actions 的 YAML 和 JSON 配置") == []


def test_extracts_expression_syntax() -> None:
    """${{ }} 表达式整段当一个标识符。"""

    assert extract_identifiers("${{ github.event_name }} 是什么") == [
        "${{ github.event_name }}"
    ]


def test_deduplicates_and_keeps_first_case() -> None:
    """重复出现只算一次，且保留第一次出现时的大小写。"""

    assert extract_identifiers("fromJSON 和 fromjson 是一回事吗") == ["fromJSON"]


def test_case_change_is_not_a_loss() -> None:
    """大小写变了不算丢失：索引和查询两侧都会归一化，不影响命中。"""

    diff = diff_identifiers("GITHUB_TOKEN 的权限", "github_token 的权限范围是什么")

    assert diff.lost == []
    assert [t.lower() for t in diff.kept] == ["github_token"]


def test_translated_identifier_counts_as_loss() -> None:
    """标识符被翻译成中文 = 丢失，这正是 Query Rewrite 最典型的翻车方式。"""

    diff = diff_identifiers(
        "如何启用 ACTIONS_STEP_DEBUG？", "如何开启工作流的调试日志功能？"
    )

    assert diff.lost == ["ACTIONS_STEP_DEBUG"]
    assert diff.kept == []


def test_new_identifier_is_reported_as_introduced() -> None:
    """改写后冒出原问题没有的标识符，要单独标出来供人工判断。"""

    diff = diff_identifiers(
        "怎么手动触发工作流？", "怎么用 workflow_dispatch 手动触发？"
    )

    assert diff.introduced == ["workflow_dispatch"]


def test_summary_denominator_excludes_cases_without_identifier() -> None:
    """不含标识符的题不进保留率分母——它根本谈不上"丢失"。"""

    summary = summarize_identifiers(
        [
            ("如何启用 ACTIONS_STEP_DEBUG？", "如何开启调试日志？"),  # 丢了 1 个
            ("怎么管理缓存？", "如何清理工作流缓存？"),  # 本来就没有标识符
        ]
    )

    assert summary.num_cases_with_identifier == 1
    assert summary.num_identifiers == 1
    assert summary.num_lost == 1
    assert summary.retention == 0.0
    assert summary.num_cases_with_loss == 1


def test_summary_without_any_identifier_reports_full_retention() -> None:
    """一个标识符都没有时保留率是 1.0，不是 0.0。

    报 0.0 会被读成"全丢了"，是彻头彻尾的误导。
    """

    summary = summarize_identifiers([("怎么管理缓存？", "如何清理缓存？")])

    assert summary.num_identifiers == 0
    assert summary.retention == 1.0
