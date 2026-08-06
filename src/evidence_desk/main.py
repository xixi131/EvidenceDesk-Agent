"""FastAPI 应用入口。"""

from fastapi import FastAPI

from evidence_desk.api.exception_handlers import register_exception_handlers
from evidence_desk.api.middleware.request_context import request_context_middleware
from evidence_desk.api.routers.health import router as health_router
from evidence_desk.application.readiness import ReadinessService
from evidence_desk.core.config import get_settings
from evidence_desk.core.logging import configure_logging
from evidence_desk.infrastructure.readiness import check_dependencies

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="可评测的企业技术支持与工单协同 Agent",
)
app.state.readiness_service = ReadinessService(check_dependencies)
app.middleware("http")(request_context_middleware)
register_exception_handlers(app)
app.include_router(health_router)
