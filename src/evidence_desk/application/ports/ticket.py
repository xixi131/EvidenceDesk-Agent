"""支持工单（Ticket）端口及其数据契约。

应用层只依赖这个端口来「创建或取回一张工单」，不关心背后是真实 Postgres
还是测试用的假实现——跟 github.py 里 GitHubGateway 是同一个思路。
"""

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class _TicketModel(BaseModel):
    """本端口数据契约的公共基类：拒绝未知字段，保持我们自己的干净结构。"""

    model_config = ConfigDict(extra="forbid")


class Ticket(_TicketModel):
    """一张支持工单的关键字段。"""

    id: int
    idempotency_key: str
    title: str
    description: str
    context_summary: str
    status: str
    created_at: datetime


class TicketRepository(Protocol):
    """创建/去重支持工单的最小接口。"""

    def create_or_get(
        self,
        *,
        idempotency_key: str,
        title: str,
        description: str,
        context_summary: str,
    ) -> tuple[Ticket, bool]:
        """按 idempotency_key 创建一张工单；已存在则直接返回原工单。

        返回 (ticket, is_new)：is_new 为 True 表示这次真的新建了一条，
        False 表示命中了已有工单（重复请求，没有产生新记录）。
        """
        ...
