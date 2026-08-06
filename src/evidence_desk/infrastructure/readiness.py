"""PostgreSQL 和 Weaviate 的外部就绪探测。"""

import asyncio
import logging

import httpx
import psycopg

from evidence_desk.core.config import Settings

logger = logging.getLogger("evidence_desk.dependencies")


async def check_postgresql(settings: Settings) -> str:
    """验证 PostgreSQL 能否接受并执行简单查询。"""

    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url,
            connect_timeout=2,
        ) as connection:
            await connection.execute("SELECT 1")
        return "ok"
    except Exception as exc:
        logger.warning(
            "PostgreSQL 就绪检查失败",
            extra={"error_code": "POSTGRESQL_UNAVAILABLE"},
            exc_info=exc,
        )
        return "unavailable"


async def check_weaviate(settings: Settings) -> str:
    """验证 Weaviate 是否报告为就绪状态。"""

    try:
        async with httpx.AsyncClient(
            base_url=settings.weaviate_url,
            timeout=2,
        ) as client:
            response = await client.get("/v1/.well-known/ready")
        if response.status_code == 200:
            return "ok"
        return "unavailable"
    except Exception as exc:
        logger.warning(
            "Weaviate 就绪检查失败",
            extra={"error_code": "WEAVIATE_UNAVAILABLE"},
            exc_info=exc,
        )
        return "unavailable"


async def check_dependencies(settings: Settings) -> dict[str, str]:
    """并发检查所有必要依赖。"""

    postgresql, weaviate = await asyncio.gather(
        check_postgresql(settings),
        check_weaviate(settings),
    )
    return {"postgresql": postgresql, "weaviate": weaviate}
