"""证据约束回答用例：只依据检索到的官方资料作答。

这一层负责三件事：
1. 无证据时直接拒答（连大模型都不调用），避免凭空编造；
2. 有证据时，把检索到的 Chunk 拼成「参考资料」，用系统指令把模型锁死在资料范围内；
3. 组装指向真实 Chunk 的引用，并记录本次使用的 Prompt 版本。

它只依赖 ``LLMClient`` 端口，不关心背后是真 OpenAI 还是测试假模型。
"""

from dataclasses import dataclass

from evidence_desk.application.ports import LLMClient
from evidence_desk.rag.citations import build_citations, parse_citation_markers
from evidence_desk.rag.models import Citation, RetrievalHit

# Prompt 一旦改动就升版本号，让每条评测结果能追溯到「当时用的哪版提示词」。
# v2（P6-06）：新增行内引用标号要求。改造动机见 rag/citations.py 的模块注释——
# v1 的「来源」只是检索结果的去重列表，不看回答文本，用户无法核实哪句话来自哪篇。
ANSWER_PROMPT_VERSION = "answer-v2"

# 没有证据时统一的拒答话术，同时用作系统指令里的固定兜底回答。
NO_EVIDENCE_REPLY = "知识库中没有找到相关信息，无法回答该问题。"

SYSTEM_PROMPT = (
    "你是 GitHub Actions 技术支持助手。"
    "你只能依据用户消息中提供的『参考资料』回答问题，"
    "不得使用参考资料以外的知识，也不得猜测或编造。"
    f"如果参考资料不足以回答，必须原样回答：「{NO_EVIDENCE_REPLY}」。"
    "回答使用简体中文，简洁、准确，只回答问题本身。"
    # 以下为 v2 新增的引用规则。写得这么细是因为标号一旦标错（越界、张冠李戴、
    # 该标不标），引用就从「证据」变成「伪造的证据」——比没有引用更糟。
    "\n\n引用规则（必须遵守）："
    "\n1. 每一个事实性陈述句的末尾，必须标出它依据的资料编号，格式为 [1]、[2]。"
    "\n2. 编号就是参考资料前面的那个序号（[资料1] 对应 [1]），"
    "不得使用参考资料编号范围以外的数字。"
    "\n3. 一句话同时依据多条资料时，连着标，例如 [1][3]。"
    "\n4. 不得凭空标注：只有该资料确实支撑这句话时才标它。"
    "\n5. 过渡句、总起句可以不标；但凡是陈述事实、给出步骤或参数的句子都必须标。"
)


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """一次证据约束回答的结果。"""

    answer: str
    citations: list[Citation]
    answered: bool
    prompt_version: str


class RagAnswerService:
    """根据检索到的 Chunk 生成带引用、受证据约束的回答。"""

    def __init__(
        self,
        llm: LLMClient,
        *,
        temperature: float,
        prompt_version: str = ANSWER_PROMPT_VERSION,
    ) -> None:
        self._llm = llm
        self._temperature = temperature
        self._prompt_version = prompt_version

    def answer(self, question: str, hits: list[RetrievalHit]) -> AnswerResult:
        """把问题和检索结果变成一段有据可查的回答。"""

        # 第一道防线：没有任何检索证据时，直接拒答，不浪费一次模型调用。
        if not hits:
            return AnswerResult(
                answer=NO_EVIDENCE_REPLY,
                citations=[],
                answered=False,
                prompt_version=self._prompt_version,
            )

        user_prompt = self._build_user_prompt(question, hits)
        text = self._llm.complete(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            temperature=self._temperature,
        ).strip()

        # 第二道防线：模型判断资料不足、给出兜底拒答时，不附带引用。
        answered = NO_EVIDENCE_REPLY not in text
        # v2：先读出回答里标了哪些 [n]，再据此筛出引用。
        # 注意这里**不做纠错**——模型没标任何标号时 citations 就是空的，
        # 模型标了越界编号时那条被跳过。这两种都是真实的失败模式，
        # 要留给 Citation Correctness 指标去测，不能在生产侧悄悄抹平。
        citations = (
            build_citations(hits, parse_citation_markers(text)) if answered else []
        )

        return AnswerResult(
            answer=text,
            citations=citations,
            answered=answered,
            prompt_version=self._prompt_version,
        )

    @staticmethod
    def _build_user_prompt(question: str, hits: list[RetrievalHit]) -> str:
        """把 Top-K Chunk 拼成带编号的「参考资料」正文，附上问题。"""

        blocks: list[str] = []
        for position, hit in enumerate(hits, start=1):
            section = " > ".join(hit.section_path)
            blocks.append(
                f"[资料{position}] 标题：{hit.title}\n"
                f"章节：{section}\n"
                f"来源：{hit.source_url}\n"
                f"内容：{hit.content}"
            )
        context = "\n\n".join(blocks)
        return (
            f"参考资料：\n{context}\n\n"
            f"用户问题：{question}\n\n"
            "请只依据以上参考资料回答。"
        )
