from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import FeedbackPolicySettings
from app.recommendations.candidates import Candidate
from app.recommendations.feedback import FeedbackInputs, apply_feedback_policy


NOW = datetime(2026, 8, 2, tzinfo=timezone.utc)


def item(item_id, genres=(), cast=()):
    return Candidate("movie", item_id, ("content",), {}, {
        "genreIds": list(genres), "cast": list(cast)
    })


def event(item_id, event_type, value=None, days=0):
    return {
        "mediaType": "movie", "mediaId": item_id, "eventType": event_type,
        "value": value, "createdAt": NOW - timedelta(days=days),
    }


def test_exact_exclusions_respect_latest_state_and_user_preferences() -> None:
    interactions = (
        event("no", "not_interested"),
        event("low", "rating_submit", 4),
        event("rated", "rating_submit", 8),
        event("fav", "favourite_add"),
        event("removed", "favourite_add", days=2),
        event("removed", "favourite_remove", days=1),
        event("viewed", "detail_view"),
    )
    result = apply_feedback_policy(
        [item(value) for value in ("no", "low", "rated", "fav", "removed", "viewed", "seed")],
        FeedbackInputs(interactions, {}),
        seed_item_key="movie:seed", now=NOW,
    )

    assert {candidate.item_key for candidate in result.candidates} == {
        "movie:removed", "movie:viewed"
    }
    assert result.excluded_reasons["movie:no"] == ("not_interested",)
    assert set(result.excluded_reasons["movie:low"]) == {"low_rating", "previously_rated"}
    assert result.excluded_reasons["movie:seed"] == ("current_seed",)
    assert result.negative_penalties["movie:removed"] == 0.6


def test_configured_favourites_and_ratings_can_remain_but_low_rating_cannot() -> None:
    inputs = FeedbackInputs(
        (event("rated", "rating_submit", 8), event("low", "rating_submit", 2), event("fav", "favourite_add")),
        {}, exclude_previously_favourited=False, exclude_previously_rated=False,
    )
    result = apply_feedback_policy(
        [item("rated"), item("low"), item("fav")], inputs, now=NOW
    )
    assert {candidate.item_key for candidate in result.candidates} == {
        "movie:rated", "movie:fav"
    }


def test_recent_clicks_and_repeated_impressions_are_seen_not_watched() -> None:
    interactions = (
        event("clicked", "recommendation_click"),
        event("shown", "recommendation_impression"),
        event("shown", "recommendation_impression", days=1),
        event("shown", "recommendation_impression", days=2),
        event("old", "recommendation_click", days=30),
        event("view", "detail_view"),
    )
    result = apply_feedback_policy(
        [item(value) for value in ("clicked", "shown", "old", "view")],
        FeedbackInputs(interactions, {}), now=NOW,
    )
    assert result.seen_penalties == {"movie:clicked": 0.35, "movie:shown": 0.5}
    assert len(result.candidates) == 4


def test_similarity_penalties_require_repeated_evidence_and_are_capped() -> None:
    interactions = (
        event("bad1", "not_interested"),
        event("bad2", "rating_submit", 2),
    )
    metadata = {
        "movie:bad1": {"genreIds": [18], "cast": ["Actor"]},
        "movie:bad2": {"genreIds": [18], "cast": ["Actor"]},
    }
    result = apply_feedback_policy(
        [item("candidate", genres=[18], cast=["Actor"])],
        FeedbackInputs(interactions, metadata), now=NOW,
    )
    assert result.negative_penalties["movie:candidate"] == 0.4

    single = apply_feedback_policy(
        [item("candidate", genres=[18], cast=["Actor"])],
        FeedbackInputs((interactions[0],), metadata), now=NOW,
    )
    assert single.negative_penalties == {}


def test_invalid_and_future_activity_does_not_create_recent_penalties() -> None:
    future = event("future", "recommendation_click")
    future["createdAt"] = NOW + timedelta(days=1)
    invalid = event("invalid", "recommendation_click")
    invalid["createdAt"] = "bad"
    result = apply_feedback_policy(
        [item("future"), item("invalid")], FeedbackInputs((future, invalid), {}), now=NOW
    )
    assert result.seen_penalties == {}
