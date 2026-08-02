from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "stage",
            "media_type",
            "source",
            "method",
            "path",
            "status",
            "latency_ms",
            "error_type",
            "page",
            "tmdb_id",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        for output_field in (
            "discovered",
            "fetched",
            "created",
            "updated",
            "unchanged",
            "failed",
        ):
            record_field = f"count_{output_field}"
            if hasattr(record, record_field):
                payload[output_field] = getattr(record, record_field)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
