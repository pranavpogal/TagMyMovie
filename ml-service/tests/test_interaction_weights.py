from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.collaborative.interaction_weights import (
    WEIGHT_VERSION,
    base_interaction_weight,
    collaborative_confidence,
    rating_weight,
    recency_multiplier,
    weighted_signal,
)


@pytest.mark.parametrize(
    ("rating", "expected"),
    [(1, -3), (3, -3), (3.5, -1), (5, -1), (5.5, 0), (7, 2), (8.5, 2), (9, 3), (10, 3)],
)
def test_rating_bands_are_centralized_and_explicit(rating, expected) -> None:
    assert rating_weight(rating) == expected


def test_base_weights_and_version_are_stable() -> None:
    assert WEIGHT_VERSION == "interaction-weights-v1"
    assert base_interaction_weight("detail_view") == 0.2
    assert base_interaction_weight("favourite_add") == 4
    assert base_interaction_weight("not_interested") == -4
    assert base_interaction_weight("recommendation_impression") == 0
    assert collaborative_confidence("detail_view") == 0.1
    assert collaborative_confidence("search_click") == 0.3
    assert collaborative_confidence("rating_submit", 9) == 3
    assert collaborative_confidence("rating_submit", 4) == 0
    assert collaborative_confidence("not_interested") == 0


def test_recency_decay_uses_fractional_days_and_never_boosts_future_events() -> None:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert recency_multiplier(now - timedelta(days=10), now=now, decay_factor=0.98) == pytest.approx(0.98**10)
    assert recency_multiplier(now + timedelta(days=1), now=now, decay_factor=0.98) == 1

    signal = weighted_signal(
        {
            "mediaId": "1",
            "mediaType": "movie",
            "eventType": "trailer_play",
            "createdAt": now - timedelta(days=2),
        },
        now=now,
        decay_factor=0.98,
    )
    assert signal is not None
    assert signal.media_key == "movie:1"
    assert signal.weight == pytest.approx(0.98**2)
