from app.core.config import Settings
from scripts import smoke_langfuse


class FakeClient:
    def __init__(self, authenticated: bool = True) -> None:
        self.authenticated = authenticated
        self.flushed = False

    def auth_check(self) -> bool:
        return self.authenticated

    def flush(self) -> None:
        self.flushed = True


class FakeSpan:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def __enter__(self) -> "FakeSpan":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)


class FakeTracer:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.spans: list[dict[str, object]] = []
        self.span_obj = FakeSpan()

    def span(self, name: str, **kwargs: object) -> FakeSpan:
        self.spans.append({"name": name, **kwargs})
        return self.span_obj


def _configured_settings() -> Settings:
    return Settings(
        langfuse_enabled=True,
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_host="https://cloud.langfuse.com",
    )


def test_langfuse_smoke_refuses_missing_configuration(capsys) -> None:
    exit_code = smoke_langfuse.run_smoke(
        settings=Settings(
            langfuse_enabled=False,
            langfuse_public_key="",
            langfuse_secret_key="",
            langfuse_base_url="",
            langfuse_host="",
        )
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "LANGFUSE_ENABLED" in output
    assert "LANGFUSE_PUBLIC_KEY" in output
    assert "LANGFUSE_SECRET_KEY" in output


def test_langfuse_smoke_sends_metadata_only_span(monkeypatch, capsys) -> None:
    fake_client = FakeClient()
    fake_tracer = FakeTracer(client=fake_client)
    monkeypatch.setattr(smoke_langfuse, "build_tracer", lambda settings: fake_tracer)

    exit_code = smoke_langfuse.run_smoke(
        settings=_configured_settings(),
        span_name="test.langfuse_smoke",
    )

    assert exit_code == 0
    assert fake_client.flushed is True
    assert fake_tracer.spans[0]["name"] == "test.langfuse_smoke"
    assert fake_tracer.spans[0]["metadata"]["content_policy"] == "metadata_only"
    assert fake_tracer.span_obj.updates[0]["output"] == {
        "status": "passed",
        "prompt_logged": False,
        "document_logged": False,
        "answer_logged": False,
    }
    output = capsys.readouterr().out
    assert "Langfuse smoke test passed." in output
    assert "metadata only" in output


def test_langfuse_smoke_fails_when_auth_check_rejects(monkeypatch, capsys) -> None:
    fake_tracer = FakeTracer(client=FakeClient(authenticated=False))
    monkeypatch.setattr(smoke_langfuse, "build_tracer", lambda settings: fake_tracer)

    exit_code = smoke_langfuse.run_smoke(settings=_configured_settings())

    assert exit_code == 1
    assert "credentials were rejected" in capsys.readouterr().out
