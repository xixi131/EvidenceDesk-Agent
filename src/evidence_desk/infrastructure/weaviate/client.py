"""创建 Weaviate 客户端连接。"""

from urllib.parse import urlparse

import weaviate

from evidence_desk.core.config import Settings


def connect_to_weaviate(settings: Settings) -> weaviate.WeaviateClient:
    """根据应用配置连接本机 Docker 中的 Weaviate。"""

    parsed_url = urlparse(settings.weaviate_url)
    if parsed_url.hostname is None:
        raise ValueError(f"WEAVIATE_URL 无效：{settings.weaviate_url}")

    return weaviate.connect_to_local(
        host=parsed_url.hostname,
        port=parsed_url.port or 8080,
        grpc_port=settings.weaviate_grpc_port,
    )
