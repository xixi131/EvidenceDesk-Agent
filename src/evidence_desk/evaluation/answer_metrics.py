"""回答层评测指标（P6-06）。

跟 metrics.py（检索指标）、agent_metrics.py（Agent 指标）是同一个约定：
纯函数，不碰 IO、不调模型，只做「拿到一题的结果，判断这一题对不对」。
汇总成比例是脚本的事。

本轮只实现 Refusal Accuracy，后面三个指标（Answer Correctness /
Faithfulness / Citation Correctness）陆续加进来。
"""

from evidence_desk.application.refusal import detect_refusal

# detect_refusal 从 application 层导入再原样导出：生产和评测必须用**同一份**
# 拒答判定逻辑，各写一份迟早出现「评测说拒答了、生产说没拒答」的分裂。
# 这里保留这个名字，是为了让评测侧的调用方不用关心它实际住在哪一层。
__all__ = [
    "detect_refusal",
    "has_citation",
    "missed_refusal",
    "out_of_range_markers",
    "over_refusal",
    "refusal_correct",
    "retrieval_hit",
]


def retrieval_hit(relevant_doc_ids: list[str], retrieved_doc_ids: list[str]) -> bool:
    """这次检索有没有捞到任何一篇标注的相关文档。

    用来给「误拒」归因。实测发现 4 道误拒里有 1 道（dev-037）压根没捞到正确
    文档——模型手里全是无关资料，说「答不了」是**正确行为**，不该算生成层的错。
    两种误拒要分开报：

    - 检索没捞到 → 该调检索（换 Hybrid、开重排）
    - 检索捞到了还不答 → 该调提示词

    合并成一个数字会把这两条完全相反的修复方向糊在一起。
    """

    return bool(set(relevant_doc_ids) & set(retrieved_doc_ids))


def refusal_correct(should_answer: bool, answered: bool) -> bool:
    """判断这一题的「答 / 不答」决策是否正确。

    should_answer：数据集标注的真值——知识库里到底有没有答案。
    answered：系统实际的行为。

    两个布尔值相等就算对。汇总成比例就是 Refusal Accuracy。

    这个指标测的是整条拒答链路的综合表现，而拒答现在是分层的
    （见 application/refusal.py）：第 0 层检索置信度闸门直接拦掉，
    第 2 层从回答文本里认出拒答意图。所以某一题判错时，
    要先看它是被哪一层处理的，才知道该去修哪儿。
    """

    return should_answer == answered


def over_refusal(should_answer: bool, answered: bool) -> bool:
    """该答却拒答了（误拒）。返回 True 表示发生了这类错误。"""

    return should_answer and not answered


def out_of_range_markers(markers: list[int], num_hits: int) -> list[int]:
    """回答里标了、但参考资料根本没有的编号（越界引用）。

    Citation Correctness 的**结构性**部分——纯规则就能查，不用 Judge：
    只有 5 条资料却标了 [7]，这是确定无疑的错误，用户点进去什么都没有。

    分成结构性和语义性两层，是因为前者免费且百分百准确，
    没道理为它多花一次模型调用。语义性那层（「[2] 指向的资料真的支撑这句话吗」）
    才需要 Judge。
    """

    return [m for m in markers if not 1 <= m <= num_hits]


def has_citation(markers: list[int]) -> bool:
    """回答里到底标没标引用。

    「该引不引」是 Citation Correctness 的另一种失败：一句结论光秃秃地摆着，
    用户没有任何核实途径。它不报错、看起来也正常，只有专门统计才发现得了。
    """

    return bool(markers)


def missed_refusal(should_answer: bool, answered: bool) -> bool:
    """不该答却答了（漏拒）。返回 True 表示发生了这类错误。

    为什么要把两类错误分开数，而不是只报一个 Refusal Accuracy：
    **它们的严重程度差着量级。**

    - 误拒（over_refusal）：知识库里明明有，系统却说「没找到」。
      用户体验差，但用户不会被误导——他知道自己没得到答案，会换个问法
      或者去查文档。

    - 漏拒（missed_refusal）：知识库里根本没有，系统却编了一段出来，
      **而且底下还挂着几条官方链接当证据**。用户没有任何线索知道这是编的，
      反而因为有引用而更加相信。这是安全事故，不是体验问题。

    两者合并成一个准确率，等于把「体验瑕疵」和「安全事故」按同样的权重
    混在一起——85% 的准确率背后，是误拒撑的还是漏拒撑的，意义完全不同。
    所以报告里必须分开列。
    """

    return not should_answer and answered
