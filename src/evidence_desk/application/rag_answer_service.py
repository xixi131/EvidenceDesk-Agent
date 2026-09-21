"""证据约束回答用例：只依据检索到的官方资料作答。

这一层负责三件事：
1. 无证据时直接拒答（连大模型都不调用），避免凭空编造；
2. 有证据时，把检索到的 Chunk 拼成「参考资料」，用系统指令把模型锁死在资料范围内；
3. 组装指向真实 Chunk 的引用，并记录本次使用的 Prompt 版本。

它只依赖 ``LLMClient`` 端口，不关心背后是真 OpenAI 还是测试假模型。
"""

import logging
from dataclasses import dataclass

from evidence_desk.application.ports import LLMClient
from evidence_desk.application.refusal import detect_refusal
from evidence_desk.rag.citations import build_citations, parse_citation_markers
from evidence_desk.rag.models import Citation, RetrievalHit

logger = logging.getLogger("evidence_desk.answer")

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
        min_score: float = 0.0,
    ) -> None:
        # min_score 是第 0 层闸门：检索 Top-1 相关度低于它就直接拒答，
        # 连模型都不调。默认 0.0 等于不设闸门——老调用方（测试、脚本）
        # 不传这个参数时行为完全不变，改动才能安全上线。
        self._llm = llm
        self._temperature = temperature
        self._prompt_version = prompt_version
        self._min_score = min_score

    def answer(self, question: str, hits: list[RetrievalHit]) -> AnswerResult:
        """把问题和检索结果变成一段有据可查的回答。"""

        # 第 0 层（前置闸门）：证据不够就直接拒答，连模型都不调。
        #
        # 这一层最可靠，因为它**完全不依赖模型的行为**——分数是检索器算出来的
        # 客观数字，模型再怎么不听话也影响不了它。顺带还省一次模型调用。
        #
        # 注意判断条件不能只写 `if not hits`：向量检索固定返回 top_k 条，
        # 问「今天天气怎么样」它照样捞 5 条无关文档回来，hits 从不为空，
        # 那个 if 永远不会触发。必须看**分数**，不是看条数。
        if not hits or hits[0].score < self._min_score:
            if hits:
                logger.info(
                    "检索置信度不足，前置拒答",
                    extra={"top_score": hits[0].score, "min_score": self._min_score},
                )
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

        # 第 2 层（文本兜底）：从回答文本里认出拒答意图。
        #
        # 原来这里是 `NO_EVIDENCE_REPLY not in text`——一字不差的精确匹配，
        # 模型少个句号或换个说法就误判。更根本的问题是那等于**把程序的状态判断
        # 交给一段自然语言**，而措辞由模型决定、不受我们控制。
        # 换成 detect_refusal（去标点 + 多模式 + 长度兜底），跟评测侧共用同一份逻辑。
        #
        # 这一层本该只是兜底，主判断应该是第 1 层（让模型返回结构化的
        # can_answer 字段）。第 1 层要改整个输出格式，本版未做，记在 ADR 里。
        answered = not detect_refusal(text)

        # v2：先读出回答里标了哪些 [n]，再据此筛出引用。
        # 这里**不做纠错**——模型没标任何标号时 citations 就是空的，
        # 标了越界编号时那条被跳过。两种都是真实的失败模式，
        # 要留给 Citation Correctness 指标去测，不能在生产侧悄悄抹平。
        markers = parse_citation_markers(text)
        citations = build_citations(hits, markers) if answered else []

        # 第 3 层（后置校验）：声称回答了，却一个引用标号都没标。
        #
        # 说明它没引用任何资料就给出了答案——要么在凭预训练知识作答，
        # 要么其实在拒答只是没说清。**只打日志，不改判**：它有正常的例外
        # （纯过渡性回答、寒暄），直接改判会误伤。先积累观测数据，
        # 等看清真实发生率再决定要不要升级成硬判断。
        if answered and not markers:
            logger.warning("回答未标注任何引用", extra={"error_code": "NO_CITATION"})

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
