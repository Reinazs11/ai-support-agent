import logging
import sys

import structlog

from app.core.config import Settings

SENSITIVE_THIRD_PARTY_LOGGERS = ("openai", "httpx", "httpcore")


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.app_debug else logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.app_debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )
    for logger_name in SENSITIVE_THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
