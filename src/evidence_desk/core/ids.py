"""请求 ID 和链路追踪 ID 辅助函数。"""

from uuid import uuid4


def new_request_id() -> str:
    """生成简短且便于检索的请求 ID。"""

    return f"req_{uuid4().hex}"
