"""阶段 1C Smoke Set：批量检查正确文档能否进入 Top-K，并打印每题 Recall。"""

import json
from dataclasses import dataclass
from pathlib import Path

from evidence_desk.core.config import get_settings
from evidence_desk.infrastructure.embedding import BgeEmbeddingAdapter
from evidence_desk.infrastructure.weaviate import (
    WeaviateDenseRetriever,
    connect_to_weaviate,
    ensure_knowledge_chunk_collection,
)

SMOKE_SET_PATH = Path("data/evaluation/smoke_set_v1.jsonl")
REPORT_PATH = Path("data/evaluation/smoke_report_v1.json")


@dataclass(frozen=True)
class SmokeCase:
    """一条 Smoke 测试题。"""

    id: str
    question: str
    relevant_doc_ids: list[str]
    should_answer: bool


def load_cases(path: Path) -> list[SmokeCase]:
    """把 JSONL 一行行读成 SmokeCase 列表。"""
    cases: list[SmokeCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:  # 跳过空行
            continue
        raw = json.loads(line)  # 一行文本 → 一个 dict
        cases.append(
            SmokeCase(
                id=raw["id"],
                question=raw["question"],
                relevant_doc_ids=raw["relevant_doc_ids"],
                should_answer=raw["should_answer"],
            )
        )
    return cases


def main() -> None:
    settings = get_settings()
    cases = load_cases(SMOKE_SET_PATH)

    embedder = BgeEmbeddingAdapter(
        settings.embedding_model, settings.embedding_cache_dir
    )
    client = connect_to_weaviate(settings)

    answerable = 0  # 有答案的题总数
    passed = 0  # 至少命中一篇的题数（门禁看这个）
    recall_sum = 0.0  # 所有有答案题的 Recall 累加，最后求平均
    records: list[dict] = []  # 每题一条记录，最后写进 JSON 报告

    try:
        collection = ensure_knowledge_chunk_collection(client)
        retriever = WeaviateDenseRetriever(collection)

        for case in cases:
            vector = embedder.embed_query(case.question)
            hits = retriever.search(vector, top_k=settings.retrieval_top_k)
            got_ids = [hit.parent_doc_id for hit in hits]

            if not case.should_answer:
                print(f"➖ [{case.id}] (无答案题) {case.question}")
                print(f"    Top-{settings.retrieval_top_k} 命中: {got_ids}")
                records.append(
                    {
                        "id": case.id,
                        "question": case.question,
                        "should_answer": False,
                        "relevant_doc_ids": case.relevant_doc_ids,
                        "retrieved": [
                            {
                                "rank": hit.rank,
                                "chunk_id": hit.chunk_id,
                                "parent_doc_id": hit.parent_doc_id,
                                "score": round(hit.score, 4),
                            }
                            for hit in hits
                        ],
                    }
                )
                continue

            answerable += 1
            matched = [doc_id for doc_id in case.relevant_doc_ids if doc_id in got_ids]
            recall = len(matched) / len(case.relevant_doc_ids)
            recall_sum += recall
            if matched:
                passed += 1

            mark = "✅" if matched else "❌"
            print(
                f"{mark} [{case.id}] "
                f"Recall {len(matched)}/{len(case.relevant_doc_ids)}  "
                f"{case.question}"
            )
            print(f"    期望文档: {case.relevant_doc_ids}")
            print(f"    命中文档: {got_ids}")
            records.append(
                {
                    "id": case.id,
                    "question": case.question,
                    "should_answer": True,
                    "relevant_doc_ids": case.relevant_doc_ids,
                    "matched_doc_ids": matched,
                    "recall": round(recall, 4),
                    "retrieved": [
                        {
                            "rank": hit.rank,
                            "chunk_id": hit.chunk_id,
                            "parent_doc_id": hit.parent_doc_id,
                            "score": round(hit.score, 4),
                        }
                        for hit in hits
                    ],
                }
            )

    finally:
        client.close()

    avg_recall = recall_sum / answerable if answerable else 0.0

    report = {
        "top_k": settings.retrieval_top_k,
        "embedding_model": settings.embedding_model,
        "answerable": answerable,
        "passed": passed,
        "avg_recall": round(avg_recall, 4),
        "cases": records,
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"命中题数: {passed}/{answerable}")
    print(f"平均 Recall@{settings.retrieval_top_k}: {avg_recall:.2f}")
    print(f"报告已保存: {REPORT_PATH}")


if __name__ == "__main__":
    main()
