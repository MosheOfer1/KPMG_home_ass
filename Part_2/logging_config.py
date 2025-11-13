from __future__ import annotations
import logging
import os

def setup_logging(service_name: str) -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    fmt = (
        "%(asctime)s "
        f"%(levelname)s {service_name} "
        "request_id=%(request_id)s "
        "%(name)s - %(message)s"
    )

    # Configure base logging first
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=fmt,
    )

    #Ensure every LogRecord has request_id ---
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return record

    logging.setLogRecordFactory(record_factory)
