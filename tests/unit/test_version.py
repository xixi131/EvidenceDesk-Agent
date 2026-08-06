from evidence_desk import __version__
from evidence_desk.api.schemas.common import (
    ResponseMeta,
    SuccessResponse,
    VersionResponse,
)


def test_version_response_is_stable() -> None:
    response = SuccessResponse(
        data=VersionResponse(service="evidence-desk", version=__version__),
        meta=ResponseMeta(request_id="req_test"),
    )

    assert response.ok is True
    assert response.data.version == __version__
    assert response.error is None
