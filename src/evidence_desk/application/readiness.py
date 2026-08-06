"""服务就绪检查用例。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from evidence_desk.core.config import Settings

DependencyChecker = Callable[[Settings], Awaitable[dict[str, str]]]


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """应用层使用的依赖就绪检查结果。"""

    dependencies: dict[str, str]
    unavailable: tuple[str, ...]

    @property
    def is_ready(self) -> bool:
        """所有必要依赖均可用时返回 True。"""

        return not self.unavailable


class ReadinessService:
    """编排依赖探测并生成应用层就绪结果。"""

    def __init__(self, checker: DependencyChecker) -> None:
        self._checker = checker

    async def evaluate(self, settings: Settings) -> ReadinessResult:
        """执行依赖探测并整理不可用依赖。"""

        dependencies = await self._checker(settings)
        unavailable = tuple(
            name for name, status in dependencies.items() if status != "ok"
        )
        return ReadinessResult(
            dependencies=dependencies,
            unavailable=unavailable,
        )
