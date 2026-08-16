"""从环境变量集中加载应用配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from evidence_desk import __version__


class Settings(BaseSettings):
    """EvidenceDesk Agent 服务的运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "EvidenceDesk Agent"
    app_version: str = __version__
    log_level: str = "INFO"

    database_url: str = "postgresql://localhost:5432/evidence_desk"
    weaviate_url: str = "http://localhost:8080"
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)

    github_api_base_url: str = "https://api.github.com"
    github_api_version: str = "2026-03-10"
    github_token: str | None = None

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_cache_dir: Path = Path(".cache/huggingface")
    retrieval_top_k: int = Field(default=5, ge=1, le=50)

    # 回答生成（阶段 1C 证据约束回答）。
    # API Key 只从环境/.env 读取，绝不写进代码或提交进仓库。
    openai_api_key: str | None = None
    answer_model: str = "gpt-4o-mini"
    answer_temperature: float = Field(default=0.0, ge=0.0, le=2.0)


@lru_cache
def get_settings() -> Settings:
    """为当前进程返回一个缓存的配置对象。"""

    return Settings()
