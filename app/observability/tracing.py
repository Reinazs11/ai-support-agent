from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

import structlog

logger = structlog.get_logger(__name__)


@contextmanager
def timed_span(name: str, **metadata: object) -> Iterator[None]:
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        logger.info("span_finished", span=name, elapsed_ms=round(elapsed_ms, 2), **metadata)
