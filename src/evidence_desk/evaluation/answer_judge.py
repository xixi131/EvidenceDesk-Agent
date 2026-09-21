"""LLM Judge：用一个模型给回答打分（P6-06 的 Faithfulness / Answer Quality / Citation）。

## 为什么必须用模型来判

回答是自由文本，同一个正确答案有无数种说法，字符串相等完全失效：
    「构件默认保留 90 天」 vs 「工件会被保留三个月左右（90 天）」——都对，但 != 。
向量相似度也不行：「保留 90 天」和「保留 30 天」的向量几乎重合，而差的就是那个数字。
所以只能让一个能读懂语言的东西来判，这就是 LLM-as-Judge。

## 这里判三件事，而且它们是分开的

- **Faithfulness（忠实度）**：回答里的每句话，能不能在**给模型的那几条资料**里
  找到依据。它**不关心答案对不对**，只关心有没有超出资料范围。
  「答案是对的，但那是模型从预训练知识里掏出来的，资料里根本没有」——这一格
  只有 Faithfulness 照得出来，而它是 RAG 最危险的失败：底下还挂着官方链接
  当证据，用户毫无察觉。

- **Answer Quality（回答质量）**：回答有没有真正解决用户的问题。

- **Citation Support（引用正确性）**：回答里的 [n] 标号，是否指向真正支撑该句的资料。
  只判语义那一半——结构性错误（标号越界、一个标号都没标）是纯规则就能查的，
  见 answer_metrics 的 out_of_range_markers / has_citation，不该多花一次模型调用。

## 这一版是「无参考」判法（reference-free）

判 Answer Quality 标准做法是拿**人工写的标准答案**对照，但那要为 51 道题手写
标准答案。这一版没有，所以改成让 judge 依据「问题 + 检索到的资料」判断回答
是否解决了问题。

代价要说清楚：**资料里本身就没有答案时，这个指标判不出来**——judge 只能
看到资料，看不到客观真理。所以它衡量的是「在给定资料下答得好不好」，
不是「答得对不对」。真正的 Answer Correctness 需要标准答案，留作已知限制。

## 已知风险（报告里要声明）

1. **自我偏好**：judge 和被评模型如果是同一个，会给自己人打高分。默认用同一个
   模型只是图省事，评的时候要意识到这一点。
2. **分数漂移**：温度设 0 降低随机性，但不能消除。
3. **judge 本身没被验证过**：正经做法是人工标一小批金标准、算一致率达标了才敢用。
   这一版没做，所以报告必须附人工抽查样本，看过才算数。
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from evidence_desk.application.ports import LLMClient
from evidence_desk.evaluation.jsonl import iter_json_objects
from evidence_desk.rag.models import RetrievalHit

# v2：新增 citation_support 维度（配合 answer-v2 的行内引用标号）。
JUDGE_PROMPT_VERSION = "judge-v2"

SYSTEM_PROMPT = (
    "你是一个严格、保守的 RAG 系统评测员。"
    "你要评估一段由 RAG 系统生成的回答。"
    "\n\n你只能依据给定的『参考资料』做判断，不得使用你自己的知识补全或纠正。"
    "如果回答里的某个说法在参考资料中找不到依据，即使你认为它在现实中是对的，"
    "也必须判定为没有依据——这正是本次评测要抓的问题。"
    "\n\n你需要输出三项判断："
    "\n1. faithfulness（忠实度）：回答中的事实性陈述是否都能在参考资料里找到依据。"
    "\n   - supported：全部有依据"
    "\n   - partially_supported：大部分有依据，但有个别说法找不到"
    "\n   - unsupported：主要内容都找不到依据"
    "\n2. answer_quality（回答质量）：回答是否真正解决了用户的问题。"
    "\n   - correct：准确且完整地回答了问题"
    "\n   - partial：方向对但不完整，或答偏了一部分"
    "\n   - incorrect：没有回答问题，或与参考资料矛盾"
    "\n3. citation_support（引用正确性）：回答中的 [n] 标号是否指向真正支撑该句的资料。"
    "\n   逐句检查：带标号的句子，它标的那条资料里是否确实有这个信息。"
    "\n   - supported：所有标号都指向真正支撑该句的资料"
    "\n   - partially_supported：个别标号指错了资料"
    "\n   - unsupported：标号基本都对不上"
    "\n   - no_citation：回答里一个标号都没有"
    "\n\n只输出一个 JSON 对象，不要加解释、不要加代码块标记："
    '\n{"faithfulness": "...", "unsupported_claims": ["找不到依据的原句，没有就空数组"], '
    '"answer_quality": "...", "citation_support": "...", '
    '"reason": "一句话理由，三项判断各说一句"}'
)


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    """judge 对一道题的判定。"""

    case_id: str
    faithfulness: str
    unsupported_claims: list[str]
    answer_quality: str
    # P6-06 第四个指标：[n] 标号是否指向真正支撑该句的资料。
    # 结构性错误（越界、该引不引）由 answer_metrics 的规则函数查，不占 Judge 名额；
    # 这里只判 Judge 才判得了的那部分——语义上对不对得上。
    citation_support: str
    reason: str
    # 模型的原始输出。解析失败时靠它排查，不然你只知道"失败了"却不知道它吐了什么。
    raw: str

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "case_id": self.case_id,
                "faithfulness": self.faithfulness,
                "unsupported_claims": self.unsupported_claims,
                "answer_quality": self.answer_quality,
                "citation_support": self.citation_support,
                "reason": self.reason,
                "raw": self.raw,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json_line(cls, line: str) -> "JudgeVerdict":
        return cls.from_dict(json.loads(line))

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "JudgeVerdict":
        return cls(
            case_id=str(data["case_id"]),
            faithfulness=str(data["faithfulness"]),
            unsupported_claims=[
                str(c) for c in cast(list[object], data["unsupported_claims"])
            ],
            answer_quality=str(data["answer_quality"]),
            citation_support=str(data.get("citation_support", "parse_error")),
            reason=str(data["reason"]),
            raw=str(data["raw"]),
        )


def build_judge_prompt(question: str, answer: str, hits: Sequence[RetrievalHit]) -> str:
    """拼出给 judge 看的那段正文：参考资料 + 问题 + 待评回答。

    资料编号跟生成时用的一致（[资料1]…），这样 judge 说"资料 3 里没有"时
    你能直接对上号。
    """

    blocks = [
        f"[资料{position}] {hit.title}\n{hit.content}"
        for position, hit in enumerate(hits, start=1)
    ]
    return (
        "参考资料：\n" + "\n\n".join(blocks) + "\n\n"
        f"用户问题：{question}\n\n"
        f"待评回答：{answer}\n\n"
        "请按系统指令输出 JSON。"
    )


def _parse(case_id: str, text: str) -> JudgeVerdict:
    """把模型输出解析成结构化判定；解析失败不抛异常，记成 parse_error。

    为什么不抛异常：60 道题跑到第 50 道时因为一条输出格式不对而整个崩掉，
    前面 50 次调用就白花了。记下来继续跑，最后在报告里统计有多少条没解析成功——
    解析失败率本身就是一个该被看见的数字。
    """

    cleaned = text.strip()
    # 模型爱套 ```json ... ``` 代码块，提示词里禁了也不保证遵守，这里统一剥掉。
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return JudgeVerdict(
            case_id, "parse_error", [], "parse_error", "parse_error", "", text
        )

    return JudgeVerdict(
        case_id=case_id,
        faithfulness=str(data.get("faithfulness", "parse_error")),
        unsupported_claims=[str(c) for c in data.get("unsupported_claims", [])],
        answer_quality=str(data.get("answer_quality", "parse_error")),
        citation_support=str(data.get("citation_support", "parse_error")),
        reason=str(data.get("reason", "")),
        raw=text,
    )


class AnswerJudge:
    """调一次 LLM，给一道题的回答打分。"""

    def __init__(self, llm: LLMClient, *, temperature: float = 0.0) -> None:
        # 温度 0：判卷必须尽量可复现。同一份答案跑两次给不同结论的话，
        # 指标就没有意义了。（注意这只能降低漂移，不能消除。）
        self._llm = llm
        self._temperature = temperature

    def judge(
        self,
        case_id: str,
        question: str,
        answer: str,
        hits: Sequence[RetrievalHit],
    ) -> JudgeVerdict:
        text = self._llm.complete(
            system=SYSTEM_PROMPT,
            user=build_judge_prompt(question, answer, hits),
            temperature=self._temperature,
        )
        return _parse(case_id, text)


def append_verdict(verdict: JudgeVerdict, path: Path) -> None:
    """追加一条判定并立刻刷盘，支持断点续传。

    跟 answer_runner.append_run 同理：judge 要调 48 次模型，
    中途服务抖一下就前功尽弃。每判完一条就落盘，崩了能接着跑。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(verdict.to_json_line() + "\n")
        handle.flush()


def save_verdicts(verdicts: Sequence[JudgeVerdict], path: Path) -> None:
    """判定结果也存成 JSONL —— judge 调用同样很贵，同样只跑一次。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(v.to_json_line() for v in verdicts) + "\n", encoding="utf-8"
    )


def load_verdicts(path: Path) -> list[JudgeVerdict]:
    """读回判定结果。跟 load_run 一样用容错解析，防被编辑器格式化弄坏。"""

    return [
        JudgeVerdict.from_dict(raw)
        for raw in iter_json_objects(path.read_text(encoding="utf-8"))
    ]
