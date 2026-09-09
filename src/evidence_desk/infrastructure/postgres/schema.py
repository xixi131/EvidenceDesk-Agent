"""Postgres 业务表的建表脚本（P4-04）。

只建 tickets 一张表——feedback / evaluation_runs / evaluation_case_results /
prompt_versions 是阶段 6（评测）才会用到的表，现在没有任何代码会写它们，
先不建（等真正要用再建，避免表建了却没人用）。
"""

import psycopg

_CREATE_TICKETS_TABLE = """
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    context_summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def ensure_ticket_table(database_url: str) -> None:
    """确保 tickets 表存在（服务启动时调用一次）。

    跟 weaviate.py 里 ensure_knowledge_chunk_collection 是同一个用途：
    「没有就建，有就跳过」，用的是 IF NOT EXISTS，天然幂等，重复调用无副作用。
    """

    with psycopg.connect(database_url) as connection:
        connection.execute(_CREATE_TICKETS_TABLE)
