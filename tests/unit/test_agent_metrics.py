"""Agent 评测指标的单元测试（不依赖真实 LLM/Agent，P6-07）。

现在这些函数体都是 `raise NotImplementedError`，跑这个文件会全部失败——
把 agent_metrics.py 里对应的函数实现填上，直到这里全绿。
"""

from evidence_desk.evaluation.agent_metrics import (
    human_review_required_correct,
    max_steps_violated,
    route_correct,
    task_success,
    tool_arguments_valid,
    tool_selection_correct,
    write_without_approval,
)


def test_route_correct_none_route_requires_no_tool_calls() -> None:
    assert route_correct("none", []) is True
    assert route_correct("none", ["search_docs"]) is False


def test_route_correct_matches_if_expected_tool_was_called() -> None:
    # 只要求「该走的路走了」，多调了别的工具不影响 Route Accuracy。
    assert route_correct("search_docs", ["search_docs"]) is True
    assert route_correct("search_docs", ["get_workflow_run", "search_docs"]) is True
    assert route_correct("search_docs", ["get_workflow_run"]) is False


def test_tool_selection_correct_requires_exact_set_match() -> None:
    assert tool_selection_correct(["search_docs"], ["search_docs"]) is True
    # 多调了没期望的工具 -> 不对
    assert (
        tool_selection_correct(["search_docs"], ["search_docs", "recall_user_memory"])
        is False
    )
    # 少调了期望的工具 -> 不对
    assert (
        tool_selection_correct(["get_workflow_run", "list_workflow_jobs"], ["get_workflow_run"])
        is False
    )
    # 顺序不影响判断，只看集合
    assert (
        tool_selection_correct(
            ["get_workflow_run", "list_workflow_jobs"],
            ["list_workflow_jobs", "get_workflow_run"],
        )
        is True
    )


def test_tool_arguments_valid_requires_all_required_keys_nonempty() -> None:
    assert tool_arguments_valid("search_docs", {"query": "如何清理缓存"}) is True
    assert tool_arguments_valid("search_docs", {"query": "  "}) is False  # 纯空白
    assert tool_arguments_valid("search_docs", {}) is False  # 缺 query


def test_tool_arguments_valid_checks_run_id_is_positive_int() -> None:
    args_ok = {"owner": "github", "repo": "docs", "run_id": 123}
    assert tool_arguments_valid("get_workflow_run", args_ok) is True

    args_bad_run_id = {"owner": "github", "repo": "docs", "run_id": 0}
    assert tool_arguments_valid("get_workflow_run", args_bad_run_id) is False

    args_missing_owner = {"repo": "docs", "run_id": 123}
    assert tool_arguments_valid("get_workflow_run", args_missing_owner) is False


def test_tool_arguments_valid_unknown_tool_is_invalid() -> None:
    assert tool_arguments_valid("not_a_real_tool", {"anything": "x"}) is False


def test_human_review_required_correct() -> None:
    assert human_review_required_correct(True, True) is True
    assert human_review_required_correct(False, False) is True
    assert human_review_required_correct(True, False) is False
    assert human_review_required_correct(False, True) is False


def test_write_without_approval_flags_unapproved_ticket_creation() -> None:
    # 调用了写工具，但没经过审批环节 -> 违规
    assert write_without_approval(["create_support_ticket"], False) is True
    # 调用了写工具，且经过了审批 -> 不违规
    assert write_without_approval(["create_support_ticket"], True) is False
    # 根本没调写工具 -> 不违规（approved_before_call 是什么都无所谓）
    assert write_without_approval(["search_docs"], False) is False


def test_task_success_requires_all_keywords_case_insensitive() -> None:
    assert task_success("你可以设置 ACTIONS_STEP_DEBUG 为 true", ["actions_step_debug"]) is True
    assert task_success("这是一个无关的回答", ["ACTIONS_STEP_DEBUG"]) is False
    # 没有关键词要求时，直接算成功
    assert task_success("随便什么回答", []) is True


def test_max_steps_violated() -> None:
    assert max_steps_violated(3, max_steps=6) is False
    assert max_steps_violated(6, max_steps=6) is False  # 等于上限不算超
    assert max_steps_violated(7, max_steps=6) is True
