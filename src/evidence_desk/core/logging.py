"""应用结构化日志配置。"""

import json
import logging
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """将选定日志字段渲染为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "request_id",
            "method",
            "path",
            "status_code",
            "latency_ms",
            "error_code",
            # 一次 Agent 调用的开销（agent/usage.py 采集，agent 路由负责记录）。
            # 跟上面的 HTTP 字段共用同一条白名单：想上日志的字段必须先登记在
            # 这里，避免哪天有人往 extra 里塞了 API Key 就直接进了日志。
            "conversation_id",
            "model",
            "llm_calls",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost_usd",
            "tool_calls",
            "agent_latency_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """配置服务日志记录器，并避免记录敏感值。"""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("evidence_desk")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
