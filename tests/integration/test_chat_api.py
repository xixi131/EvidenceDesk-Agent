"""POST /api/v1/chat 的集成测试。

用假的 Embedder / Retriever / LLM 直接装配 ChatService 放进 app.state，
从而在不加载真实模型、不连 Weaviate、不需要 API Key 的情况下，
验证「路由 → 服务 → 证据约束回答 → 引用」这条 HTTP 链路。
"""

import httpx
import pytest
from httpx import ASGITransport

from evidence_desk.application.chat_service import ChatService
from evidence_desk.application.rag_answer_service import RagAnswerService
from evidence_desk.main import app
from evidence_desk.rag.models import RetrievalHit


class FakeEmbedder:
    def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeRetriever:
    # 签名跟 ChunkRetriever 端口保持一致，含 query_text（Hybrid 检索必需）。
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self._hits = hits
        self.received_query_text: str | None = None

    def search(
        self, query_vector: list[float], *, top_k: int, query_text: str | None = None
    ) -> list[RetrievalHit]:
        self.received_query_text = query_text
        return self._hits[:top_k]


class FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def complete(self, *, system: str, user: str, temperature: float) -> str:
        return self.reply


def make_hit() -> RetrievalHit:
    return RetrievalHit(
        rank=1,
        distance=0.1,
        score=0.9,
        chunk_id="doc_debug_0001",
        parent_doc_id="doc_debug",
        title="启用调试日志记录",
        section_path=["启用调试日志记录"],
        content="把 ACTIONS_STEP_DEBUG 设为 true 即可开启步骤调试日志。",
        source_url="https://docs.github.com/enable-debug-logging",
    )


def install_chat_service(*, hits: list[RetrievalHit], reply: str) -> FakeRetriever:
    answer_service = RagAnswerService(FakeLLM(reply), temperature=0.0)
    retriever = FakeRetriever(hits)
    app.state.chat_service = ChatService(
        FakeEmbedder(),
        retriever,
        answer_service,
        top_k=5,
    )
    return retriever


@pytest.mark.asyncio
async def test_chat_returns_answer_with_citation() -> None:
    # 回答里必须带 [1] 标号：P6-06 之后引用不再是「把检索到的都列上」，
    # 而是只列模型自己标注过的那几条（见 rag_answer_service 的 v2 注释）。
    install_chat_service(
        hits=[make_hit()], reply="将 ACTIONS_STEP_DEBUG 设为 true。[1]"
    )

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat", json={"question": "如何开启调试日志？"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["answered"] is True
    assert body["data"]["answer"] == "将 ACTIONS_STEP_DEBUG 设为 true。[1]"
    assert body["data"]["citations"][0]["source_url"] == (
        "https://docs.github.com/enable-debug-logging"
    )
    assert body["meta"]["request_id"]


@pytest.mark.asyncio
async def test_chat_answer_without_markers_has_no_citations() -> None:
    """答了但一个标号都没标 → 照样返回答案，但引用是空的。

    这是 P6-06 有意保留的失败模式：生产侧不做纠错（不把检索到的硬塞进引用），
    让它暴露出来交给 Citation 指标去测。这条测试就是钉住这个行为，
    免得哪天有人「顺手修一下」，把真实失败率抹平了。
    """
    install_chat_service(hits=[make_hit()], reply="将 ACTIONS_STEP_DEBUG 设为 true。")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat", json={"question": "如何开启调试日志？"}
        )

    body = response.json()
    assert body["data"]["answered"] is True
    assert body["data"]["citations"] == []


@pytest.mark.asyncio
async def test_chat_without_evidence_refuses() -> None:
    install_chat_service(hits=[], reply="不该被调用")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat", json={"question": "库里没有的问题"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["answered"] is False
    assert body["data"]["citations"] == []


@pytest.mark.asyncio
async def test_chat_passes_query_text_to_the_retriever() -> None:
    """跟 search_docs 同一个回归点：漏传 query_text，生产的 Hybrid 检索就抛错。"""
    retriever = install_chat_service(hits=[make_hit()], reply="回答[1]")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/chat", json={"question": "如何开启调试日志？"})

    assert retriever.received_query_text == "如何开启调试日志？"


@pytest.mark.asyncio
async def test_chat_rejects_empty_question() -> None:
    install_chat_service(hits=[make_hit()], reply="回答")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"question": ""})

    # 空问题被 Pydantic 校验拦下，返回 422，不会进到检索。
    assert response.status_code == 422
