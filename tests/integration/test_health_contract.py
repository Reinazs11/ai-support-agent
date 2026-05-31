from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_contract(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("N8N_WEBHOOK_MODE", "simulated")
    monkeypatch.setenv("AGENT_ROUTER_PROVIDER", "deterministic")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "dependencies" in body
    assert body["dependencies"]["n8n"] == "simulated"
    assert body["dependencies"]["agent_router"] == "deterministic"
    assert body["dependencies"]["langfuse"] == "disabled"
    get_settings.cache_clear()


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


def test_health_reports_llm_agent_router_ready(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ROUTER_PROVIDER", "llm")
    monkeypatch.setenv("CHAT_PROVIDER", "openai")
    monkeypatch.setenv("CHAT_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["agent_router"] == "llm"
    get_settings.cache_clear()


def test_health_reports_llm_agent_router_blockers(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ROUTER_PROVIDER", "llm")
    monkeypatch.setenv("CHAT_PROVIDER", "disabled")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["agent_router"] == "llm_chat_provider_disabled"
    get_settings.cache_clear()

    get_settings.cache_clear()
    monkeypatch.setenv("CHAT_PROVIDER", "openai")
    monkeypatch.setenv("CHAT_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["agent_router"] == "llm_missing_api_key"
    get_settings.cache_clear()


def test_health_reports_langfuse_configuration_state(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["langfuse"] == "missing_credentials"
    get_settings.cache_clear()

    get_settings.cache_clear()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["dependencies"]["langfuse"] == "configured"
    get_settings.cache_clear()
