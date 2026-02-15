"""Integration tests for the FastAPI redaction API."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from redact_mcp.main import app
from redact_mcp.rate_limiter import SlidingWindowRateLimiter


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


# --- Health Endpoint ---


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# --- Redact Endpoint ---


class TestRedactEndpoint:
    def test_json_body(self, client):
        response = client.post(
            "/redact",
            json={"text": "Server 192.168.1.10 is up"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "mapping_id" in data
        assert "192.168.1.10" not in data["redacted_text"]
        assert data["mapping_count"] == 1

    def test_text_plain_body(self, client):
        response = client.post(
            "/redact",
            content="Router at 10.0.0.1",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "10.0.0.1" not in data["redacted_text"]
        assert data["mapping_count"] == 1

    def test_deterministic_mode(self, client):
        response = client.post(
            "/redact",
            json={"text": "Host 10.0.0.1", "mode": "deterministic"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "10.0.0.1" not in data["redacted_text"]

    def test_empty_text_rejected(self, client):
        response = client.post(
            "/redact",
            json={"text": ""},
        )
        assert response.status_code == 400

    def test_invalid_json_rejected(self, client):
        response = client.post(
            "/redact",
            content=b"not valid json{{{",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_request_id_header_present(self, client):
        response = client.post(
            "/redact",
            json={"text": "192.168.1.1"},
        )
        assert "x-request-id" in response.headers


# --- Payload Size Limit ---


class TestPayloadSizeLimit:
    def test_oversized_payload_rejected(self, client):
        huge_text = "10.0.0.1 " * 200_000  # well over 1MB
        response = client.post(
            "/redact",
            content=huge_text.encode(),
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 413

    def test_normal_payload_accepted(self, client):
        response = client.post(
            "/redact",
            json={"text": "Small payload 10.0.0.1"},
        )
        assert response.status_code == 200


# --- Exception Handling ---


class TestExceptionHandling:
    def test_500_does_not_expose_stack_trace(self, client):
        with patch(
            "redact_mcp.main.RedactorEngine.redact",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/redact",
                json={"text": "192.168.1.1"},
            )
            assert response.status_code == 500
            body = response.json()
            assert body["detail"] == "Internal server error"
            assert "boom" not in str(body)
            assert "Traceback" not in str(body)


class TestHealthReadiness:
    def test_ready_endpoint_ok(self, client):
        response = client.get("/health/ready")
        assert response.status_code == 200

    def test_ready_endpoint_failure(self, client):
        client.app.state.ready = False
        response = client.get("/health/ready")
        assert response.status_code == 503
        client.app.state.ready = True


class TestRateLimiting:
    def test_rate_limit_enforced(self, client):
        client.app.state.rate_limiter = SlidingWindowRateLimiter(2, 60)
        for _ in range(2):
            response = client.post("/redact", json={"text": "10.0.0.1"})
            assert response.status_code == 200

        response = client.post("/redact", json={"text": "10.0.0.1"})
        assert response.status_code == 429
        assert response.json()["detail"] == "Too many requests"
