"""评测数据集：定义评测题结构并从 JSONL 读取。"""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalCase:
    """一条评测题。

    与阶段 1C 的 Smoke Set 字段兼容，可直接复用同一份 JSONL。
    """

    id: str
    question: str
    relevant_doc_ids: list[str]
    should_answer: bool
    tags: list[str] = field(default_factory=list)


def load_eval_cases(path: Path) -> list[EvalCase]:
    """把 JSONL 一行行读成 EvalCase 列表。"""
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        cases.append(
            EvalCase(
                id=raw["id"],
                question=raw["question"],
                relevant_doc_ids=raw["relevant_doc_ids"],
                should_answer=raw["should_answer"],
                tags=raw.get("tags", []),
            )
        )
    return cases
