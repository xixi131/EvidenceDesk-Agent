"""Weaviate 向量库基础设施适配。"""

from evidence_desk.infrastructure.weaviate.client import connect_to_weaviate
from evidence_desk.infrastructure.weaviate.indexer import KnowledgeChunkIndexer
from evidence_desk.infrastructure.weaviate.retriever import WeaviateDenseRetriever
from evidence_desk.infrastructure.weaviate.schema import (
    KNOWLEDGE_CHUNK_COLLECTION,
    ensure_knowledge_chunk_collection,
)

__all__ = [
    "KNOWLEDGE_CHUNK_COLLECTION",
    "KnowledgeChunkIndexer",
    "WeaviateDenseRetriever",
    "connect_to_weaviate",
    "ensure_knowledge_chunk_collection",
]
