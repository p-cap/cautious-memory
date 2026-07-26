"""API contract checks that do not make a Gemini request."""

import os

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "local-test-project")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")

from fastapi.testclient import TestClient

from app.fast_api_app import app


client = TestClient(app)


def test_healthcheck_identifies_draft_only_mode() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["mode"] == "local-draft"


def test_draft_request_requires_a_page_and_request() -> None:
    response = client.post("/api/drafts", json={"page": "Home"})

    assert response.status_code == 422
