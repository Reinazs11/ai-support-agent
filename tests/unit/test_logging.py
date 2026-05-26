import logging

from app.core.config import Settings
from app.core.logging import SENSITIVE_THIRD_PARTY_LOGGERS, configure_logging


def test_configure_logging_suppresses_sensitive_third_party_debug_logs() -> None:
    for logger_name in SENSITIVE_THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    configure_logging(Settings(app_debug=True))

    for logger_name in SENSITIVE_THIRD_PARTY_LOGGERS:
        assert logging.getLogger(logger_name).level == logging.WARNING
