"""回答层评测指标（P6-06）。

跟 metrics.py（检索指标）、agent_metrics.py（Agent 指标）是同一个约定：
纯函数，不碰 IO、不调模型，只做「拿到一题的结果，判断这一题对不对」。
汇总成比例是脚本的事。

本轮只实现 Refusal Accuracy，后面三个指标（Answer Correctness /
Faithfulness / Citation Correctness）陆续加进来。
"""

import re

# 判「这段话是不是在拒答」的模式。在**去掉空白和标点之后**的文本上匹配，
# 所以模式里不写标点。
#
# 为什么不能只用 `NO_EVIDENCE_REPLY not in text` 那种精确匹配：那是一字不差的
# 比对，模型少个句号、换个说法（「抱歉，知识库里没有这方面的资料」）就会被判成
# 「正经回答了」，于是一道本来拒答正确的题被记成「漏拒」——一个假警报。
# 实测 dev-050 那批数据里已经能看到模型不完全照抄话术的倾向。
_REFUSAL_PATTERNS = [
    re.compile(r"知识库.{0,6}没有.{0,8}(相关|对应).{0,4}信息"),
    re.compile(r"无法回答"),
    re.compile(
        r"(没有|未).{0,4}(找到|检索到).{0,8}(相关|对应).{0,4}(资料|信息|内容|文档)"
    ),
    re.compile(r"(参考)?资料.{0,4}(不足|不够)"),
    re.compile(r"抱歉.{0,14}(无法|不能|没有).{0,8}(回答|提供|找到)"),
]

# 拒答话术都很短。超过这个长度还想判成拒答，多半是一段正经回答里恰好出现了
# 「无法回答」之类的字眼（比如在讲"什么情况下无法回答某类请求"），
# 不能算拒答。这是防误伤的兜底。
_MAX_REFUSAL_LENGTH = 120

_PUNCTUATION = re.compile(r"[\s、，,。.！!？?：:；;「」『』\"'“”‘’（）()\[\]【】]+")


def detect_refusal(text: str) -> bool:
    """判断一段回答是不是在拒答（容错版，替代精确字符串匹配）。

    做两件事：
    1. 去掉空白和标点再匹配，句号、逗号写不写都不影响判断；
    2. 用一组「拒答意图」模式，而不是死盯那一句固定话术，模型换个说法也认得出。

    返回 True 表示这是一次拒答。
    """

    normalized = _PUNCTUATION.sub("", text)
    if not normalized or len(normalized) > _MAX_REFUSAL_LENGTH:
        return False
    return any(pattern.search(normalized) for pattern in _REFUSAL_PATTERNS)


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
    answered：系统实际的行为——来自 AnswerResult.answered，也就是
        「模型的输出里没有出现那句固定拒答话术」。

    两个布尔值相等就算对。汇总成比例就是 Refusal Accuracy。

    顺带记一件容易搞错的事：这个指标测的**不是** RagAnswerService 里
    `if not hits: 直接拒答` 那道防线——Dense 检索永远返回 top_k 条，
    问「今天天气怎么样」它照样捞 5 条 GitHub Actions 文档回来，hits
    从不为空，那个 if 根本进不去。真正在守拒答的是系统提示词里那句
    「资料不足时必须原样回答……」。所以这个指标测的是**提示词的纪律性**。
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
