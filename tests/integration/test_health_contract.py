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
