"""回答评测的「跑批」阶段：对每道题生成一次答案，并把结果存成 run 文件（P6-06）。

为什么要把「跑」和「判」拆开：
    生成答案很贵——每题一次 LLM 调用，60 题要几分钟、要花钱。而 P6-06 有
    四个指标要实现，指标代码一定会反复改、反复写错。如果「跑」和「判」混在
    一个循环里，每改一次指标就得把 60 次 LLM 调用重跑一遍。

    所以这里只负责跑，并把判分可能用到的一切**原样**存下来（答案文本、引用、
    当时喂给模型的 chunk 正文）。之后加指标、改指标、重算，都只读这个文件，
    一次模型都不用重调。

    这也是评测工程的通用做法：贵的东西一次性产出，廉价的东西反复重算。

run 文件用 JSONL（一行一条记录），跟 dev_v1.jsonl 是同一个格式。除了「能用
head/grep 直接看」「一行坏掉不影响其余行」之外，这里还用上了它第三个好处：
**可以追加**。

这一点是被一次真实事故逼出来的：跑到一半时 LLM 服务返回 503，整个脚本崩掉，
前面已经跑完的几十道题全部丢失，钱和时间都白花。改成「每跑完一题就立刻追加
写盘 + 启动时跳过已完成的题」之后，崩了再跑一次就能从断点接上。

如果 run 文件是一个大的 JSON 数组，就做不到这件事——数组必须整体写完才合法，
中途崩掉留下的是一个语法不完整的破文件。
"""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from evidence_desk.application.chat_service import ChatService
from evidence_desk.application.rag_answer_service import ANSWER_PROMPT_VERSION
from evidence_desk.evaluation.dataset import EvalCase
from evidence_desk.evaluation.jsonl import iter_json_objects
from evidence_desk.rag.models import Citation, RetrievalHit


@dataclass(frozen=True, slots=True)
class AnswerRunRecord:
    """一道题跑完之后留下的全部痕迹。

    分成三块看：

    1. 题目本身（id/question/tags/should_answer/relevant_doc_ids）——
       从 EvalCase 原样抄过来。判分时要拿它当标准答案，存进 run 文件后，
       判分阶段就不必再去读一次数据集，一个文件自足。

    2. 生成结果（answer/answered/citations）——系统这次的输出。

    3. 现场证据（hits）——当时喂给模型的那几条 chunk，**连正文一起存**。
       这块最容易被忽略，但 Faithfulness 指标非它不可：判断「有没有编造」
       就是拿答案逐句去这些正文里找依据。事后没法补，丢了就得重跑。
    """

    id: str
    question: str
    tags: list[str]
    should_answer: bool
    relevant_doc_ids: list[str]

    answer: str
    answered: bool
    citations: list[Citation]

    hits: list[RetrievalHit]
    prompt_version: str

    def to_json_line(self) -> str:
        """序列化成 JSONL 的一行。

        Citation 和 RetrievalHit 是 Pydantic 模型，用 model_dump() 变成普通
        字典；dataclass 这一层字段本来就是基本类型，直接拼进去即可。
        """

        return json.dumps(
            {
                "id": self.id,
                "question": self.question,
                "tags": self.tags,
                "should_answer": self.should_answer,
                "relevant_doc_ids": self.relevant_doc_ids,
                "answer": self.answer,
                "answered": self.answered,
                "citations": [c.model_dump() for c in self.citations],
                "hits": [h.model_dump() for h in self.hits],
                "prompt_version": self.prompt_version,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json_line(cls, line: str) -> "AnswerRunRecord":
        """从 JSONL 的一行还原回来。"""

        return cls.from_dict(json.loads(line))

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "AnswerRunRecord":
        """从已经解析好的字典还原。

        model_validate 是 model_dump 的逆操作：字典 → Pydantic 对象，
        顺便按模型定义校验字段齐不齐、类型对不对。run 文件被手工改坏时
        会在这里直接报错，而不是等判分算出一个莫名其妙的数字。
        """

        return cls(
            id=str(raw["id"]),
            question=str(raw["question"]),
            tags=[str(t) for t in cast(list[object], raw["tags"])],
            should_answer=bool(raw["should_answer"]),
            relevant_doc_ids=[
                str(d) for d in cast(list[object], raw["relevant_doc_ids"])
            ],
            answer=str(raw["answer"]),
            answered=bool(raw["answered"]),
            citations=[
                Citation.model_validate(c) for c in cast(list[object], raw["citations"])
            ],
            hits=[
                RetrievalHit.model_validate(h) for h in cast(list[object], raw["hits"])
            ],
            prompt_version=str(raw["prompt_version"]),
        )


def iter_answers(
    cases: Sequence[EvalCase],
    chat_service: ChatService,
    *,
    prompt_version: str = ANSWER_PROMPT_VERSION,
) -> Iterator[AnswerRunRecord]:
    """逐题生成答案，**每跑完一题就产出一条**，而不是等全部跑完才返回。

    用生成器（yield）而不是返回列表，是为了让调用方能边跑边写盘。
    返回列表的话，中途抛异常时这个列表还在函数内部，调用方一条都拿不到——
    一次 503 就让前面几十次模型调用全白费。

    其余设计同 generate_answers 的说明。
    """

    for index, case in enumerate(cases, start=1):
        result = chat_service.answer_question(case.question)
        print(f"  [{index}/{len(cases)}] {case.id} 完成")
        yield AnswerRunRecord(
            id=case.id,
            question=case.question,
            tags=case.tags,
            should_answer=case.should_answer,
            relevant_doc_ids=case.relevant_doc_ids,
            answer=result.answer,
            answered=result.answered,
            citations=result.citations,
            hits=result.hits,
            prompt_version=prompt_version,
        )


def generate_answers(
    cases: Sequence[EvalCase],
    chat_service: ChatService,
    *,
    prompt_version: str = ANSWER_PROMPT_VERSION,
) -> list[AnswerRunRecord]:
    """一次性跑完所有题并返回列表（测试和小批量用）。

    大批量跑请用 iter_answers + 追加写盘，这样中途崩了不会前功尽弃。
    """

    return list(iter_answers(cases, chat_service, prompt_version=prompt_version))


def append_run(record: AnswerRunRecord, path: Path) -> None:
    """把一条记录追加到 run 文件末尾，并立刻刷盘。

    "a" 是追加模式（append）：不清空原有内容，直接写到文件末尾。
    flush() 强制把缓冲区的内容真正写进磁盘——不调它的话，内容可能还躺在
    内存缓冲里，进程一崩就没了，那这套断点续传就白做了。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.to_json_line() + "\n")
        handle.flush()


def save_run(records: Sequence[AnswerRunRecord], path: Path) -> None:
    """把跑批结果写成 JSONL。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(record.to_json_line() for record in records) + "\n",
        encoding="utf-8",
    )


def load_run(path: Path) -> list[AnswerRunRecord]:
    """读回之前跑批的结果。

    用 iter_json_objects 而不是按行切：这个文件很容易被编辑器的「保存时自动
    格式化」拍成缩进版 JSON，内容一个字没丢、只是换行位置变了，按行读就会当场
    炸掉。一份花了几十次 LLM 调用的结果不该因为被编辑器碰一下就报废。
    """

    return [
        AnswerRunRecord.from_dict(raw)
        for raw in iter_json_objects(path.read_text(encoding="utf-8"))
    ]
