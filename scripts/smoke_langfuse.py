import argparse
import sys
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import Settings
from app.observability.tracing import NoOpTracer, build_tracer

DEFAULT_SPAN_NAME = "portfolio.langfuse_smoke"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a content-minimized live Langfuse smoke test."
    )
    parser.add_argument("--span-name", default=DEFAULT_SPAN_NAME)
    args = parser.parse_args()

    return run_smoke(settings=Settings(), span_name=args.span_name)


def run_smoke(*, settings: Settings, span_name: str = DEFAULT_SPAN_NAME) -> int:
    missing_config = _missing_langfuse_config(settings)
    if missing_config:
        print(
            "Refusing to run Langfuse smoke test because configuration is incomplete: "
            f"{', '.join(missing_config)}."
        )
        print(
            "Set LANGFUSE_ENABLED=true, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, "
            "and LANGFUSE_HOST in .env."
        )
        return 1

    tracer = build_tracer(settings)
    if isinstance(tracer, NoOpTracer):
        print("Langfuse tracer is disabled; check Langfuse configuration.")
        return 1

    client = getattr(tracer, "client", None)
    if client is None or not hasattr(client, "auth_check"):
        print("Langfuse client is unavailable; cannot verify credentials.")
        return 1

    try:
        authenticated = bool(client.auth_check())
    except Exception as exc:
        print(f"Langfuse auth check failed: {type(exc).__name__}")
        return 1

    if not authenticated:
        print("Langfuse auth check failed: credentials were rejected.")
        return 1

    run_id = str(uuid4())
    timestamp = datetime.now(UTC).isoformat()
    with tracer.span(
        span_name,
        metadata={
            "smoke_test": True,
            "run_id": run_id,
            "app_env": settings.app_env,
            "content_policy": "metadata_only",
            "timestamp": timestamp,
        },
    ) as span:
        span.update(
            output={
                "status": "passed",
                "prompt_logged": False,
                "document_logged": False,
                "answer_logged": False,
            }
        )

    try:
        client.flush()
    except Exception as exc:
        print(f"Langfuse flush failed: {type(exc).__name__}")
        return 1

    print("Langfuse smoke test passed.")
    print(f"- host: {settings.langfuse_base_url or settings.langfuse_host}")
    print(f"- span_name: {span_name}")
    print(f"- run_id: {run_id}")
    print("- content: metadata only; no prompts, documents, answers, or secrets")
    return 0


def _missing_langfuse_config(settings: Settings) -> list[str]:
    missing = []
    if not settings.langfuse_enabled:
        missing.append("LANGFUSE_ENABLED")
    if not settings.langfuse_public_key:
        missing.append("LANGFUSE_PUBLIC_KEY")
    if not settings.langfuse_secret_key:
        missing.append("LANGFUSE_SECRET_KEY")
    if not settings.langfuse_host:
        missing.append("LANGFUSE_HOST")
    return missing


if __name__ == "__main__":
    sys.exit(main())
