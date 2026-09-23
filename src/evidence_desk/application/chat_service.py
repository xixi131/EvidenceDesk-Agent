"""无 Agent 的最小 RAG 问答用例。

把「问题 → 向量化 → 检索 → 证据约束回答 → 引用」这条直线串起来。
这一版没有意图路由、没有 Tool、没有 Query 改写，是阶段 1C 的穿刺闭环。

它只依赖端口（QueryEmbedder / ChunkRetriever）和 RagAnswerService，
不认识 sentence-transformers、Weaviate 或 OpenAI 的任何细节。
"""

from dataclasses import dataclass

from evidence_desk.application.ports import ChunkRetriever, QueryEmbedder
from evidence_desk.application.rag_answer_service import RagAnswerService
from evidence_desk.rag.models import Citation, RetrievalHit


@dataclass(frozen=True, slots=True)
class ChatResult:
    """一次问答的完整结果，包含回答、引用和原始检索列表。"""

    answer: str
    answered: bool
    citations: list[Citation]
    hits: list[RetrievalHit]


class ChatService:
    """编排一次证据约束的知识问答。"""

    def __init__(
        self,
        embedder: QueryEmbedder,
        retriever: ChunkRetriever,
        answer_service: RagAnswerService,
        *,
        top_k: int,
    ) -> None:
        self._embedder = embedder
        self._retriever = retriever
        self._answer_service = answer_service
        self._top_k = top_k

    def answer_question(self, question: str) -> ChatResult:
        """把用户问题变成有据可查的回答。"""

        query_vector = self._embedder.embed_query(question)
        # query_text 必须传，理由同 agent/tools.py 的 search_docs：
        # 生产检索是 Hybrid，BM25 那一半需要原始问题文本才能算关键词得分。
        hits = self._retriever.search(
            query_vector, top_k=self._top_k, query_text=question
        )
        result = self._answer_service.answer(question, hits)
        return ChatResult(
            answer=result.answer,
            answered=result.answered,
            citations=result.citations,
            hits=hits,
        )
