from app.core.config import Settings
from app.observability.tracing import NoOpTracer, build_tracer


def test_build_tracer_defaults_to_noop() -> None:
    tracer = build_tracer(Settings(langfuse_enabled=False))

    assert isinstance(tracer, NoOpTracer)


def test_build_tracer_without_langfuse_credentials_is_noop() -> None:
    tracer = build_tracer(
        Settings(
            langfuse_enabled=True,
            langfuse_public_key="",
            langfuse_secret_key="",
        )
    )

    assert isinstance(tracer, NoOpTracer)
