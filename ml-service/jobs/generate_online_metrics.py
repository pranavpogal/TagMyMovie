from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.config import EmbeddingSettings
from app.database import create_mongo_client
from app.reporting.online_metrics import generate_online_metrics


def _positive_number(name: str, default: float) -> float:
    value = float(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def main() -> int:
    load_dotenv()
    client = None
    try:
        settings = EmbeddingSettings.from_env()
        days = _positive_number("ONLINE_METRICS_LOOKBACK_DAYS", 30)
        attribution_hours = _positive_number("ONLINE_METRICS_ATTRIBUTION_HOURS", 24)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        attribution_window = timedelta(hours=attribution_hours)
        client = create_mongo_client(settings.mongodb_url)
        client.admin.command("ping")
        database = client[settings.mongodb_database]
        impressions = list(database["recommendationimpressions"].find(
            {"createdAt": {"$gte": start, "$lte": end}},
            {"_id": 0, "recommendationId": 1, "user": 1, "strategy": 1,
             "items": 1, "createdAt": 1},
        ))
        interactions = list(database["interactions"].find(
            {"createdAt": {"$gte": start, "$lte": end + attribution_window},
             "eventType": {"$in": ["recommendation_click", "favourite_add",
                                      "rating_submit", "not_interested"]}},
            {"_id": 0, "user": 1, "mediaId": 1, "mediaType": 1,
             "eventType": 1, "recommendationId": 1, "recommendationRank": 1,
             "createdAt": 1},
        ))
        catalogue_count = database["media_catalog"].count_documents(
            {"mediaType": {"$in": ["movie", "tv"]}}
        )
        report = generate_online_metrics(
            impressions, interactions, catalogue_item_count=catalogue_count,
            attribution_window=attribution_window, period_start=start, period_end=end,
        )
        output_directory = Path(os.getenv("ONLINE_METRICS_REPORT_DIRECTORY", "artifacts/reports"))
        output_directory.mkdir(parents=True, exist_ok=True)
        output = output_directory / f"online-metrics-{end.strftime('%Y%m%d-%H%M%S-%f')}.json"
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(output), **report}, indent=2))
        return 0
    except Exception as error:
        print(f"{error.__class__.__name__}: online metrics generation failed")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
