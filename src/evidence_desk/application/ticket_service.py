"""创建支持工单的用例。

跟 ChatService/RagAnswerService 一样：只编排端口（TicketRepository），
不认识 psycopg 或 Postgres 的任何细节。
"""

from evidence_desk.application.ports import Ticket, TicketRepository


class TicketService:
    """编排一次「创建或复用支持工单」的用例。"""

    def __init__(self, repository: TicketRepository) -> None:
        self._repository = repository

    def create_ticket(
        self,
        *,
        idempotency_key: str,
        title: str,
        description: str,
        context_summary: str,
    ) -> tuple[Ticket, bool]:
        """按 idempotency_key 创建（或复用）一张工单。"""

        return self._repository.create_or_get(
            idempotency_key=idempotency_key,
            title=title,
            description=description,
            context_summary=context_summary,
        )
