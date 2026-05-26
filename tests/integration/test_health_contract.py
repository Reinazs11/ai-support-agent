from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_contract() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "dependencies" in body
    assert body["dependencies"]["n8n"] == "simulated"


def test_health_reports_openai_configured_with_provider_specific_keys(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("CHAT_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["openai"] == "configured"
    get_settings.cache_clear()


def test_health_reports_live_n8n_only_when_dispatch_is_unblocked(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("N8N_WEBHOOK_MODE", "live")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example.test/webhook/support")
    monkeypatch.setenv("N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL", "false")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["n8n"] == "live"
    get_settings.cache_clear()


def test_health_reports_n8n_live_blockers(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("N8N_WEBHOOK_MODE", "live")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "")
    monkeypatch.setenv("N8N_WEBHOOK_REQUIRES_HUMAN_APPROVAL", "false")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["n8n"] == "missing_webhook_url"
    get_settings.cache_clear()
