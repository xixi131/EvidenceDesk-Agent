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

    # P6-05 重排：两段式检索里"粗筛捞多少条候选"。
    # 定成 20 是因为 Dense 的 Recall@20 = 1.0000（见 retrieval_eval_v1.md），
    # 也就是 20 条候选里必定含正确答案——粗筛不漏，重排才有意义。
    # 调小会开始漏答案，调大只是让重排白跑更多条、变慢。
    rerank_candidate_top_n: int = Field(default=20, ge=1, le=100)
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # P6-02 Query Rewrite：「失败后改写」这一组用什么信号判定"这次检索没捞好"。
    # 生产环境拿不到标准答案，不能用 Recall 判失败，只能用检索器自己给的分数：
    # Top-1 的 score 低于这个阈值就认为没把握，触发改写重查一次。
    # 默认 0.62 是个起点不是定论——脚本会打印 Top-1 分数的分布，
    # 按真实数据调完再写回这里。
    query_rewrite_score_threshold: float = Field(default=0.62, ge=0.0, le=1.0)

    # 回答生成（阶段 1C 证据约束回答）。
    # API Key 只从环境/.env 读取，绝不写进代码或提交进仓库。
    openai_api_key: str | None = None
    # 中转站/自建代理需要自定义 Base URL；留空则用 OpenAI 官方地址。
    openai_base_url: str | None = None
    answer_model: str = "gpt-4o-mini"
    answer_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # 拒答第 0 层闸门：检索 Top-1 相关度低于这个值就直接拒答，连模型都不调。
    # 这一层不依赖模型的任何行为（分数是检索器算的客观数字），是四层里最可靠的一层。
    # 0.62 来自 P6-02 的真实分数分布——落在 25 分位（0.6398）稍下方，
    # 既不会永远不触发，也不会把正常问题挡在门外。
    # 跟 query_rewrite_score_threshold 数值相同但**不共用一个配置项**：
    # 两者用途不同（一个决定拒答，一个决定要不要改写重查），将来可能各自调整。
    answer_min_score: float = Field(default=0.62, ge=0.0, le=1.0)

    # M-2 上下文超限策略：会话消息（近似）token 数达到这个阈值时，
    # ReAct Agent 会在下一次调模型前先把较早的消息摘要压缩，只保留最近
    # context_keep_messages 条原始消息 + 一段摘要文本，防止长对话把上下文塞爆。
    context_summary_trigger_tokens: int = Field(default=3000, ge=1)
    context_keep_messages: int = Field(default=6, ge=1)

    # M-3 长期用户画像记忆：recall_user_memory 工具一次最多检索几条相关的历史记忆
    # 返回给模型看，跟 retrieval_top_k 是同一个模式（都是「一次检索返回几条」）。
    long_term_memory_top_k: int = Field(default=5, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    """为当前进程返回一个缓存的配置对象。"""

    return Settings()
