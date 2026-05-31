from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal, Protocol

import structlog
from langfuse import Langfuse

if TYPE_CHECKING:
    from app.core.config import Settings

logger = structlog.get_logger(__name__)

TraceSpanType = Literal[
    "span",
    "agent",
    "tool",
    "chain",
    "retriever",
    "generation",
    "embedding",
]


class TraceSpan(Protocol):
    def update(
        self,
        *,
        metadata: Mapping[str, object] | None = None,
        output: Mapping[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        pass


class Tracer(Protocol):
    def span(
        self,
        name: str,
        *,
        span_type: TraceSpanType = "span",
        metadata: Mapping[str, object] | None = None,
    ) -> AbstractContextManager[TraceSpan]:
        pass


class NoOpTracer:
    def span(
        self,
        name: str,
        *,
        span_type: TraceSpanType = "span",
        metadata: Mapping[str, object] | None = None,
    ) -> AbstractContextManager[TraceSpan]:
        return NoOpSpan()


class NoOpSpan:
    def __enter__(self) -> NoOpSpan:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def update(
        self,
        *,
        metadata: Mapping[str, object] | None = None,
        output: Mapping[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        pass


class LangfuseTracer:
    def __init__(self, client: Langfuse) -> None:
        self.client = client

    def span(
        self,
        name: str,
        *,
        span_type: TraceSpanType = "span",
        metadata: Mapping[str, object] | None = None,
    ) -> AbstractContextManager[TraceSpan]:
        try:
            return LangfuseSpan(
                self.client.start_as_current_observation(
                    name=name,
                    as_type=span_type,
                    metadata=dict(metadata or {}),
                )
            )
        except Exception as exc:
            logger.warning(
                "trace_span_start_failed",
                span=name,
                error_type=type(exc).__name__,
            )
            return NoOpSpan()


class LangfuseSpan:
    def __init__(self, context_manager: AbstractContextManager[Any]) -> None:
        self.context_manager = context_manager
        self._span: Any | None = None

    def __enter__(self) -> LangfuseSpan:
        try:
            self._span = self.context_manager.__enter__()
        except Exception as exc:
            logger.warning("trace_span_enter_failed", error_type=type(exc).__name__)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if exc_type is not None:
            self.update(
                level="ERROR",
                status_message=str(getattr(exc_type, "__name__", exc_type)),
            )
        if self._span is None:
            return False
        try:
            return bool(self.context_manager.__exit__(exc_type, exc, traceback))
        except Exception as close_exc:
            logger.warning(
                "trace_span_close_failed",
                error_type=type(close_exc).__name__,
            )
            return False

    def update(
        self,
        *,
        metadata: Mapping[str, object] | None = None,
        output: Mapping[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        if self._span is None:
            return
        try:
            self._span.update(
                metadata=dict(metadata or {}) or None,
                output=dict(output or {}) or None,
                level=level,
                status_message=status_message,
            )
        except Exception as exc:
            logger.warning("trace_span_update_failed", error_type=type(exc).__name__)


def build_tracer(settings: Settings) -> Tracer:
    if not settings.langfuse_enabled:
        return NoOpTracer()

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning("tracing_disabled", reason="missing_langfuse_credentials")
        return NoOpTracer()

    try:
        return LangfuseTracer(
            _cached_langfuse_client(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                environment=settings.app_env,
            )
        )
    except Exception as exc:
        logger.warning(
            "tracing_disabled",
            reason="langfuse_init_failed",
            error_type=type(exc).__name__,
        )
        return NoOpTracer()


@lru_cache
def _cached_langfuse_client(
    *,
    public_key: str,
    secret_key: str,
    host: str,
    environment: str,
) -> Langfuse:
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
        environment=environment,
    )
