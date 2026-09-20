"""用 LLM 把用户问题改写成更适合检索的形式（P6-02）。

动机：用户问得口语、含糊时（"那个缓存的东西咋配"），问题文本和知识库里的
官方措辞对不上，检索可能捞不到。改写就是先让模型把问题整理成接近文档用语的
说法（"如何在 GitHub Actions 中配置依赖缓存"），再拿改写后的去检索。

但改写是**有代价的一步**，P6-02 要测的正是这三个代价：

1. 精确标识符丢失：用户问 ``ACTIONS_STEP_DEBUG``，模型改写成"调试日志开关"，
   标识符没了——这是 Query Rewrite 最典型的翻车方式，而且恰恰砸在
   exact_identifier 这类最该答准的问题上。
2. 引入虚构信息：模型自作主张补上原问题里没有的条件、版本号、动作名。
3. 额外延迟：多一次 LLM 调用，几百毫秒起步。

所以下面的系统提示词是"带着镣铐改写"：能不改就不改，标识符一个字符都不许动。
把提示词写到最好，实验才是公平的——如果连最保守的改写都还是掉分，那结论
"本项目不需要 Query Rewrite"才站得住。

这一层只依赖 LLMClient 端口，跟 RagAnswerService 是同一个模式：不认识 OpenAI，
测试里塞个假模型就能跑。
"""

from dataclasses import dataclass

from evidence_desk.application.ports import LLMClient

# 跟 ANSWER_PROMPT_VERSION 同理：提示词一改就升版本号，
# 让每条实验结果都能追溯到"当时用的哪版改写提示词"。
QUERY_REWRITE_PROMPT_VERSION = "query-rewrite-v1"

SYSTEM_PROMPT = (
    "你是检索查询改写助手，服务于一个 GitHub Actions 中文文档知识库。"
    "你的唯一任务是把用户的问题改写成更容易检索到官方文档的形式。"
    "\n\n严格遵守以下规则："
    "\n1. 原文中出现的所有英文标识符（环境变量名、上下文名、字段名、函数名、"
    "action 名、版本号等，例如 ACTIONS_STEP_DEBUG、workflow_dispatch、"
    "fromJSON、actions/checkout@v4）必须**原样保留**，大小写和下划线都不许改，"
    "更不许翻译成中文或替换成同义说法。"
    "\n2. 不许增加原问题中没有的任何具体信息——不要补版本号、不要补 action 名、"
    "不要补原问题没提到的条件或场景。你只能换说法，不能添内容。"
    "\n3. 保持原问题的意图和范围不变，不要扩大也不要缩小。"
    "\n4. 如果原问题已经足够清晰、用词已经接近文档术语，就原样返回，不要为了"
    "改写而改写。"
    "\n5. 只输出改写后的问题本身，一行纯文本。不要加引号、编号、解释或前缀。"
    "\n6. 使用简体中文（其中的英文标识符除外）。"
)

# 改写后的问题不该比原问题长太多。超过这个倍数基本意味着模型在"发挥"——
# 补了原问题没有的条件和场景，正是规则 2 禁止的事。与其把这种结果送进检索，
# 不如退回原问题。
MAX_LENGTH_RATIO = 3.0


@dataclass(frozen=True, slots=True)
class RewriteResult:
    """一次改写的结果，连同"到底用没用上"这件事一起返回。

    为什么不直接返回一个字符串：改写有好几种情况会退回原问题（模型返回空、
    输出异常长）。如果只返回字符串，调用方根本分不清拿到的是"改写后的问题"
    还是"退回来的原问题"，评测时就会把"没改写成功"的题算进"改写组"的成绩里，
    把结论搞污染。所以把这件事显式摆在返回值里，让调用方必须看见。
    """

    original: str
    rewritten: str
    # 真的改了才是 True。模型原样返回、或触发兜底退回原问题，都是 False。
    changed: bool
    # 触发兜底的原因；正常改写时为 None。用来在报告里统计"模型有多不听话"。
    fallback_reason: str | None = None


class LlmQueryRewriter:
    """调一次 LLM 把问题改写成检索友好的形式。"""

    def __init__(
        self,
        llm: LLMClient,
        *,
        temperature: float = 0.0,
        prompt_version: str = QUERY_REWRITE_PROMPT_VERSION,
    ) -> None:
        # temperature 默认 0：改写要的是稳定可复现，不是创意。同一个问题
        # 每次跑出不同的改写，实验结果就没法复现了。
        self._llm = llm
        self._temperature = temperature
        self.prompt_version = prompt_version

    def rewrite(self, question: str) -> RewriteResult:
        """返回改写后的问题；模型输出不可用时退回原问题并记下原因。"""

        if not question.strip():
            raise ValueError("question 不能为空。")

        raw = self._llm.complete(
            system=SYSTEM_PROMPT,
            user=question,
            temperature=self._temperature,
        )
        candidate = _strip_wrapping(raw)

        # 兜底一：模型返回空或只有空白。这里退回原问题是对的——检索不能拿着
        # 空字符串去跑。但必须把原因记下来，不能悄悄吞掉（跟 RerankingRetriever
        # 那里"没有 query_text 就报错"是同一个原则：不制造看不见的降级）。
        if not candidate:
            return RewriteResult(question, question, False, "模型返回空")

        # 兜底二：输出异常长，基本是模型在补原问题没有的内容。
        if len(candidate) > len(question) * MAX_LENGTH_RATIO:
            return RewriteResult(question, question, False, "改写结果过长")

        return RewriteResult(question, candidate, candidate != question, None)


def _strip_wrapping(text: str) -> str:
    """去掉模型爱加的外层包装：空白、成对引号、末尾换行。

    提示词里已经要求"只输出问题本身"，但模型时不时还是会套一层引号
    （「如何……」/ "如何……"）。这种噪声直接带进检索会影响分词和匹配，
    在进入下游之前统一洗掉，比指望提示词百分百被遵守可靠。
    """

    cleaned = text.strip()
    # 只取第一行：偶尔模型会在问题后面追加解释，规则 5 明令禁止但不保证遵守。
    cleaned = cleaned.splitlines()[0].strip() if cleaned else ""

    pairs = [('"', '"'), ("'", "'"), ("「", "」"), ("“", "”"), ("《", "》")]
    for left, right in pairs:
        if len(cleaned) >= 2 and cleaned.startswith(left) and cleaned.endswith(right):
            cleaned = cleaned[1:-1].strip()
            break

    return cleaned
