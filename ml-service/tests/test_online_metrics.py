from datetime import datetime, timedelta, timezone

import pytest

from app.reporting.online_metrics import generate_online_metrics


NOW = datetime(2026, 8, 2, 12, tzinfo=timezone.utc)


def impression(recommendation_id="rec-1", strategy="personalized_hybrid"):
    return {"recommendationId": recommendation_id, "user": "user-1",
            "strategy": strategy, "createdAt": NOW,
            "items": [{"mediaId": "10", "mediaType": "movie", "rank": 2},
                      {"mediaId": "20", "mediaType": "movie", "rank": 5}]}


def event(event_type, media_id="10", *, recommendation_id=None, rank=None, hours=1):
    return {"user": "user-1", "mediaId": media_id, "mediaType": "movie",
            "eventType": event_type, "recommendationId": recommendation_id,
            "recommendationRank": rank, "createdAt": NOW + timedelta(hours=hours)}


def test_reports_required_rates_rank_coverage_and_strategy_distribution():
    interactions = [
        event("recommendation_click", recommendation_id="rec-1", rank=2),
        event("recommendation_click", recommendation_id="rec-1", rank=2),
        event("favourite_add"),
        event("rating_submit", media_id="20"),
        event("not_interested", media_id="20", recommendation_id="rec-1"),
    ]
    report = generate_online_metrics(
        [impression()], interactions, catalogue_item_count=100,
        period_start=NOW - timedelta(hours=1), period_end=NOW + timedelta(hours=2),
    )
    metrics = report["metrics"]
    assert metrics["recommendationClickThroughRate"] == 0.5
    assert metrics["favouriteAddRateAfterRecommendation"] == 0.5
    assert metrics["ratingSubmissionRateAfterRecommendation"] == 0.5
    assert metrics["notInterestedRate"] == 0.5
    assert metrics["recommendedCatalogueCoverage"] == 0.02
    assert metrics["averageRecommendationRankClicked"] == 2
    assert metrics["strategyUsageDistribution"]["personalized_hybrid"] == {"count": 1, "share": 1}
    assert report["counts"]["recentItemAttributions"] == 2
    assert "do not establish causal impact" in report["interpretation"]


def test_rejects_cross_user_direct_ids_and_events_outside_attribution_window():
    wrong_user = event("recommendation_click", recommendation_id="rec-1")
    wrong_user["user"] = "other-user"
    late = event("favourite_add", hours=25)
    report = generate_online_metrics(
        [impression()], [wrong_user, late], catalogue_item_count=10,
        period_start=NOW - timedelta(hours=1), period_end=NOW + timedelta(hours=30),
        attribution_window=timedelta(hours=24),
    )
    assert report["counts"]["attributedClicks"] == 0
    assert report["counts"]["attributedFavouriteAdds"] == 0


def test_empty_period_returns_warning_and_null_rates():
    report = generate_online_metrics(
        [], [], catalogue_item_count=0,
        period_start=NOW - timedelta(days=1), period_end=NOW,
    )
    assert report["warning"] == "no recommendation impressions in the reporting period"
    assert report["metrics"]["recommendationClickThroughRate"] is None
    assert report["metrics"]["recommendedCatalogueCoverage"] is None


def test_invalid_report_period_is_rejected():
    with pytest.raises(ValueError, match="period"):
        generate_online_metrics([], [], catalogue_item_count=1,
                                period_start=NOW, period_end=NOW)
