"""用 Postgres 实现应用层的 TicketRepository 端口（P4-05）。

跟 GitHubRestClient 一样：把底层细节（psycopg 的连接/事务/SQL）关在这个
适配器里，应用层只看得到 TicketRepository 这个抽象接口。

区别于 GitHubRestClient 常驻一个 httpx.Client：这里每次调用都临时开一个
新连接。原因是 FastAPI 的同步路由跑在线程池里，多个请求可能并发调用到这个
仓储，而裸的 psycopg.Connection 不是线程安全的——常驻一个连接给多个线程共用
会有并发冲突风险。建工单是低频操作，每次开关连接的开销可以接受，先用最简单
可靠的方式；写入量真的上来了再考虑引入连接池（psycopg_pool），现在不提前做。
"""

from typing import Any

import psycopg

from evidence_desk.application.ports.ticket import Ticket
from evidence_desk.core.errors import AppError

_INSERT_OR_SKIP = """
INSERT INTO tickets (idempotency_key, title, description, context_summary)
VALUES (%(idempotency_key)s, %(title)s, %(description)s, %(context_summary)s)
ON CONFLICT (idempotency_key) DO NOTHING
RETURNING id, idempotency_key, title, description, context_summary, status, created_at
"""

_SELECT_BY_KEY = """
SELECT id, idempotency_key, title, description, context_summary, status, created_at
FROM tickets
WHERE idempotency_key = %(idempotency_key)s
"""

_COLUMNS = (
    "id",
    "idempotency_key",
    "title",
    "description",
    "context_summary",
    "status",
    "created_at",
)


class PostgresTicketRepository:
    """用 Postgres 实现「创建或复用工单」这个端口（结构上满足 TicketRepository）。"""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create_or_get(
        self,
        *,
        idempotency_key: str,
        title: str,
        description: str,
        context_summary: str,
    ) -> tuple[Ticket, bool]:
        params = {
            "idempotency_key": idempotency_key,
            "title": title,
            "description": description,
            "context_summary": context_summary,
        }
        try:
            with psycopg.connect(self._database_url) as connection:
                # with connection.transaction()：INSERT 和「没插进去就去 SELECT」
                # 这两步共享同一个事务，中途任何一步抛异常都会整体回滚，
                # 不会出现「表面上没建成，其实半成品已经落库」的中间状态。
                with connection.transaction():
                    row = connection.execute(_INSERT_OR_SKIP, params).fetchone()
                    if row is not None:
                        return self._row_to_ticket(row), True
                    # 没有返回行 = 撞上了 UNIQUE 约束（ON CONFLICT DO NOTHING
                    # 生效），说明这个 idempotency_key 已经建过工单了，
                    # 取出那条已有记录直接复用，不当作新建。
                    existing = connection.execute(_SELECT_BY_KEY, params).fetchone()
                    if existing is None:  # pragma: no cover - 理论上不会发生
                        raise AppError(
                            code="TICKET_CREATE_RACE",
                            message="工单创建冲突后未能取回记录",
                            status_code=500,
                        )
                    return self._row_to_ticket(existing), False
        except psycopg.OperationalError as exc:
            raise AppError(
                code="TICKET_DB_UNAVAILABLE",
                message="工单数据库暂时不可用",
                status_code=502,
                retryable=True,
            ) from exc

    @staticmethod
    def _row_to_ticket(row: tuple[Any, ...]) -> Ticket:
        values = dict(zip(_COLUMNS, row, strict=True))
        return Ticket(
            id=values["id"],
            idempotency_key=values["idempotency_key"],
            title=values["title"],
            description=values["description"],
            context_summary=values["context_summary"],
            status=values["status"],
            created_at=values["created_at"],
        )
