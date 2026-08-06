"""从环境变量集中加载应用配置。"""

from functools import lru_cache

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

    github_api_base_url: str = "https://api.github.com"
    github_api_version: str = "2026-03-10"
    github_token: str | None = None

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    retrieval_top_k: int = Field(default=5, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    """为当前进程返回一个缓存的配置对象。"""

    return Settings()
