import logging
import sys

import structlog
from asgi_correlation_id import correlation_id


def add_correlation_id(logger, method_name, event_dict):
    """Injects the request ID into the structured log dictionary."""
    req_id = correlation_id.get()
    if req_id:
        event_dict["request_id"] = req_id
    return event_dict

def setup_logging(log_level: str = "INFO"):
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level),
        stream=sys.stdout,
    )
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_correlation_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
