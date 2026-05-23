import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def disable_live_providers_by_default(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "disabled")
    monkeypatch.setenv("CHAT_PROVIDER", "disabled")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    monkeypatch.setenv("CHAT_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
