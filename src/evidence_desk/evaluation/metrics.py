"""检索评测指标：Recall@K、Precision@K、MRR（文档级）。

约定（与路线图 P2-02 一致）：
- 检索返回 Top-K 个 chunk，映射成父文档 ID 的有序列表 ``ranked_doc_ids``（保留重复）；
- 命中按『唯一相关父文档』计数；
- Recall@K 分母是相关文档总数，Precision@K 分母固定是 K；
- MRR 使用第一个命中相关文档的 chunk 排名。
"""

from collections.abc import Sequence


def _relevant_hits(
    ranked_doc_ids: Sequence[str], relevant: set[str], k: int
) -> set[str]:
    """Top-K chunk 里命中的『唯一相关父文档』集合。"""
    return {doc_id for doc_id in ranked_doc_ids[:k] if doc_id in relevant}


def recall_at_k(ranked_doc_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """该找到的相关文档，进了 Top-K 的比例。分母 = 相关文档总数。"""
    if not relevant:
        raise ValueError("relevant 不能为空：Recall 需要至少一个相关文档")
    return len(_relevant_hits(ranked_doc_ids, relevant, k)) / len(relevant)


def precision_at_k(ranked_doc_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """返回的 K 个里有几个相关。分母固定 = K。"""
    if k <= 0:
        raise ValueError("k 必须为正整数")
    return len(_relevant_hits(ranked_doc_ids, relevant, k)) / k


def reciprocal_rank(ranked_doc_ids: Sequence[str], relevant: set[str]) -> float:
    """第一个命中相关文档的排名的倒数；一个都没命中则为 0。"""
    for rank, doc_id in enumerate(ranked_doc_ids, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def group_recall_by_tag(
    tagged_recalls: Sequence[tuple[list[str], float]],
) -> dict[str, float]:
    """按标签分组，算每个标签下的平均 Recall（P6-03）。

    tagged_recalls：每一项是 (这道题的 tags 列表, 这道题在某个 K 下算出来的
    recall 值) 这样一个二元组——不直接依赖 CaseResult（那个类在 runner.py，
    这里如果导入会跟 runner.py 反过来依赖 metrics.py 形成循环导入），调用方
    自己把 CaseResult 拆成这种最朴素的元组列表传进来。

    一条题可能同时有多个 tag（比如 ["multi_document", "security"]），要把
    它的 recall 值计入它拥有的**每一个**标签的分组里，不是只算一个。

    返回：{标签: 这个标签下所有题目 recall 的平均值}。如果某个标签下一题
    都没有，不应该出现在返回的字典里（不要出现"分母是 0"的情况）。
    """
    # 第一步：先把"一堆孤立的 (tags, recall)"按标签分桶，桶用字典存——
    # 键是标签名，值是一个列表，装着「目前为止见过的、属于这个标签的 recall 值」。
    # 比如跑到一半可能长这样：{"knowledge": [1.0, 0.5], "security": [0.0]}
    buckets: dict[str, list[float]] = {}

    # 外层循环：遍历每一道题的 (tags, recall) 这一对。
    for tags, recall in tagged_recalls:
        # 内层循环：一道题可能同时有好几个标签，这个 recall 值要计入它拥有的
        # 每一个标签的桶里，不是只选一个——所以要对 tags 这个列表再遍历一次。
        for tag in tags:
            # setdefault(tag, [])：如果 tag 这个键还没在 buckets 里出现过
            # （比如第一次遇到 "security"），就先给它建一个空列表再返回；
            # 如果已经出现过，直接返回那个已有的列表——不管哪种情况，
            # 返回的都是"这个标签对应的列表"，直接 append 追加当前 recall 值。
            buckets.setdefault(tag, []).append(recall)

    # 第二步：把每个标签桶里"一串 recall 值"变成"一个平均值"。
    # sum(values) / len(values) 就是最朴素的求平均：加起来除以个数。
    # 用字典推导式一次性对 buckets 里的每一个 (标签, 列表) 都算一遍。
    #
    # 边界情况顺带说明：如果 tagged_recalls 是空列表，上面的循环一次都不会
    # 执行，buckets 从头到尾都是空字典，这里推导式遍历空字典也什么都不做，
    # 自然返回 {}——不需要专门写 if 判断空输入。
    return {tag: sum(values) / len(values) for tag, values in buckets.items()}
