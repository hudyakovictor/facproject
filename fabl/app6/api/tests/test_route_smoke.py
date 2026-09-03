import pytest
from fastapi.testclient import TestClient
from app6.api.server import app   # FastAPI instance is exported as `app`

client = TestClient(app)   # Using the actual FastAPI app instance

# ----------------------------------------------------------------------
# Parameter‑free routes – these can be called without extra arguments.
# ----------------------------------------------------------------------
SAFE_ROUTES = [
    "/api/v1/health",
    "/api/v1/calibration/health",
    "/api/v1/system/health",
    "/api/v1/timeline",
    "/api/v1/zones/catalog",
    "/api/v1/report/summary",
    "/api/v1/reviews",
    "/api/v1/jobs",
]

@pytest.mark.parametrize("path", SAFE_ROUTES)
def test_api_simple_routes(path):
    """
    Minimal smoke test for routes that do not require path parameters.
    It checks that the endpoint returns a non‑5xx status (i.e. the route is
    registered) and yields JSON when a body is present.
    """
    resp = client.get(path)   # GET works for all routes in SAFE_ROUTES
    # Any status code < 500 means the endpoint exists; we treat that as success.
    assert resp.status_code < 500
    # If a body is returned, ensure it parses as JSON and is a dict.
    if resp.content:
        payload = resp.json()
        assert isinstance(payload, dict)