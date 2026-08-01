from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter


def test_json_formatter_maps_namespaced_catalogue_counts() -> None:
    record = logging.LogRecord(
        name="catalogue",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="complete",
        args=(),
        exc_info=None,
    )
    record.stage = "complete"
    record.count_created = 3
    record.count_failed = 1

    payload = json.loads(JsonFormatter().format(record))

    assert payload["stage"] == "complete"
    assert payload["created"] == 3
    assert payload["failed"] == 1
    assert "count_created" not in payload
