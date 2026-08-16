import pytest
from fastapi.testclient import TestClient
from app6.api.server import app   # FastAPI instance is exported as `app`

client = TestClient(app)   # Using the actual FastAPI app instance

# ----------------------------------------------------------------------
# Parameterized routes – we provide minimal valid placeholders to verify
# that the endpoint is registered and returns a JSON payload (or 404).
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "path,method,placeholders",
    [
        ("/api/v1/photos/{photo_id}", "get", {"photo_id": "test123"}),
        ("/api/v1/photos/{photo_id}/artifacts/{name}", "get", {"photo_id": "test123", "name": "original.jpg"}),
        ("/api/v1/photos/{photo_id}/image", "get", {"photo_id": "test123"}),
        ("/api/v1/photos/{photo_id}/landmarks/{count}/{space}", "get", {"photo_id": "test123", "count": "106", "space": "raw"}),
        ("/api/v1/photos/{photo_id}/mesh", "get", {"photo_id": "test123"}),
        ("/api/v1/photos/{photo_id}/skin_zones", "get", {"photo_id": "test123"}),
        ("/api/v1/photos/{photo_id}/info_keys", "get", {"photo_id": "test123"}),
        ("/api/v1/photos/{photo_id}/skin_zones", "get", {"photo_id": "test123"}),
        ("/api/v1/jobs/{job_id}", "get", {"job_id": "job001"}),
        ("/api/v1/jobs/{job_id}/cancel", "post", {"job_id": "job001"}),
        ("/api/v1/compare", "post", {}),  # no path params, but POST‑only
        ("/api/v1/compare/full_mesh", "post", {}),
        ("/api/v1/compare/upload", "post", {}),
        ("/api/v1/data/clear", "post", {}),
        ("/api/v1/settings/reset", "post", {}),
        ("/api/v1/reports/{name}", "get", {"name": "summary"}),
    ],
)
def test_parameterized_routes(path, method, placeholders):
    """
    Smoke test for routes that require path (or body) parameters.
    The test only checks that the endpoint can be invoked without raising
    a 5xx error and that the response, when present, is parsable JSON.
    """
    # Resolve placeholders into the URL
    for key, val in placeholders.items():
        path = path.replace(f"{{{key}}}", val)

    resp = getattr(client, method.lower())(path)
    # Treat any status < 500 as “the route exists”.
    assert resp.status_code < 500, f"{method.upper()} {path} returned {resp.status_code}"
    if resp.content:
        payload = resp.json()
        assert isinstance(payload, dict)