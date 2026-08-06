"""应用层就绪检查服务测试。"""

from evidence_desk.application.readiness import ReadinessService
from evidence_desk.core.config import Settings


async def test_readiness_service_returns_ready_when_all_dependencies_are_ok() -> None:
    """所有依赖正常时应返回就绪结果。"""

    async def fake_checker(settings: Settings) -> dict[str, str]:
        return {"postgresql": "ok", "weaviate": "ok"}

    service = ReadinessService(fake_checker)
    result = await service.evaluate(Settings(_env_file=None))

    assert result.is_ready is True
    assert result.unavailable == ()


async def test_readiness_service_collects_unavailable_dependencies() -> None:
    """依赖异常时应保留具体的不可用服务名称。"""

    async def fake_checker(settings: Settings) -> dict[str, str]:
        return {"postgresql": "ok", "weaviate": "unavailable"}

    service = ReadinessService(fake_checker)
    result = await service.evaluate(Settings(_env_file=None))

    assert result.is_ready is False
    assert result.unavailable == ("weaviate",)
