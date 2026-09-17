"""定义第一版 KnowledgeChunk Collection。"""

import weaviate
from weaviate.classes.config import Configure, DataType, Property, Tokenization

KNOWLEDGE_CHUNK_COLLECTION = "KnowledgeChunk"

# BM25/Hybrid 关键词检索要搜的字段（P6-03）。
#
# 必须显式指定：Weaviate 默认会搜遍所有可搜索的 text 字段，那样就会搜到没分过
# 词的原始 content/title 上去，中文照样匹配不上。检索器统一从这里取字段名，
# 避免两个 Retriever 各写一份、改的时候漏掉一个。
BM25_QUERY_PROPERTIES = ["content_tokens", "title_tokens"]


def ensure_knowledge_chunk_collection(
    client: weaviate.WeaviateClient,
    *,
    recreate: bool = False,
) -> weaviate.collections.Collection:
    """创建自带向量的 KnowledgeChunk Collection。"""

    if recreate and client.collections.exists(KNOWLEDGE_CHUNK_COLLECTION):
        client.collections.delete(KNOWLEDGE_CHUNK_COLLECTION)

    if not client.collections.exists(KNOWLEDGE_CHUNK_COLLECTION):
        client.collections.create(
            name=KNOWLEDGE_CHUNK_COLLECTION,
            vector_config=Configure.Vectors.self_provided(),
            properties=[
                Property(
                    name="chunk_id",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="parent_doc_id",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                # title/content 保持默认分词，只当作"原文"存着供展示和引用。
                # 中文关键词检索不走这两个字段，走下面的 *_tokens（原因见
                # rag/tokenization.py：Weaviate 内置中文分词器会造成索引端和
                # 查询端切词不一致，BM25 直接 0 命中）。
                Property(
                    name="title",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="section_path",
                    data_type=DataType.TEXT_ARRAY,
                    skip_vectorization=True,
                ),
                Property(
                    name="content",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                # *_tokens：由应用侧 segment() 切好、用空格连起来的词串，
                # 专供 BM25/Hybrid 检索（P6-03）。
                #
                # tokenization=WHITESPACE 是这个方案的关键：它让 Weaviate
                # **只按空格切，什么都不猜**——不认词典、不做大小写归一、不去
                # 标点。把"聪明"全部收回到应用侧的 segment() 里，索引端和查询端
                # 就必然一致。选 WHITESPACE 而不是默认的 WORD，是因为 WORD 会
                # 额外按非字母数字字符再切一刀并转小写，等于在我们切好的结果上
                # 又动了一次手——多一道我们控制不了的变换，就多一处失配风险。
                Property(
                    name="title_tokens",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                    tokenization=Tokenization.WHITESPACE,
                ),
                Property(
                    name="content_tokens",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                    tokenization=Tokenization.WHITESPACE,
                ),
                Property(
                    name="source_url",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="dataset_version",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                Property(
                    name="embedding_model",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                ),
                # 记录建索引时用的分词方案版本（rag/tokenization.py 的
                # TOKENIZER_VERSION）。分词方案一变，索引里的 token 就全变了，
                # 必须重建索引——把版本号存进来，才能随时查出"索引是哪一版建的"，
                # 而不是等到检索莫名其妙查不到东西时再回头猜。
                # FIELD 分词 = 整个值当一个 token，适合这种精确比对的元数据。
                Property(
                    name="tokenizer_version",
                    data_type=DataType.TEXT,
                    skip_vectorization=True,
                    tokenization=Tokenization.FIELD,
                ),
            ],
        )

    return client.collections.get(KNOWLEDGE_CHUNK_COLLECTION)
