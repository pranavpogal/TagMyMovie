from datetime import datetime, timedelta, timezone

from app.evaluation.offline import MODEL_NAMES, evaluate_rankings, time_based_split


NOW = datetime(2026, 8, 2, tzinfo=timezone.utc)


def interaction(user, item, day):
    return {"user": user, "mediaId": item, "mediaType": "movie",
            "eventType": "favourite_add", "value": 1,
            "createdAt": NOW + timedelta(days=day)}


def test_time_split_holds_out_latest_positive_without_future_leakage():
    values = [interaction("u1", "old", 1), interaction("u1", "middle", 2),
              interaction("u1", "latest", 3), interaction("u2", "only", 4)]
    split = time_based_split(values, minimum_interactions=3)
    assert split.eligible_users == ("u1",)
    assert split.test_by_user == {"u1": ("movie:latest",)}
    assert {value["mediaId"] for value in split.training if value["user"] == "u1"} == {"old", "middle"}
    assert any(value["user"] == "u2" for value in split.training)
    assert split.cold_start_items == 1


def test_insufficient_sample_warns_and_does_not_publish_metrics():
    split = time_based_split([interaction("u1", str(index), index) for index in range(3)],
                             minimum_interactions=3)
    recommenders = {name: lambda user, k: [] for name in MODEL_NAMES}
    report = evaluate_rankings(split, recommenders, {}, minimum_evaluation_users=2)
    assert report["warning"].startswith("insufficient evaluation sample")
    assert all(value is None for value in report["models"].values())


def test_all_required_ranking_and_catalogue_metrics_are_reported():
    interactions = []
    catalogue = {}
    for user_index in range(2):
        user = f"u{user_index}"
        for item_index in range(3):
            key = f"{user}-{item_index}"
            interactions.append(interaction(user, key, item_index))
            catalogue[f"movie:{key}"] = {"genreIds": [item_index + 1]}
    split = time_based_split(interactions, minimum_interactions=3)
    recommenders = {name: (lambda user, k: list(split.test_by_user[user])) for name in MODEL_NAMES}
    report = evaluate_rankings(split, recommenders, catalogue, k=10, minimum_evaluation_users=2)
    metrics = report["models"]["hybrid_with_diversity"]
    assert metrics["recallAt10"] == metrics["hitRateAt10"] == 1
    assert metrics["ndcgAt10"] == metrics["mapAt10"] == metrics["mrrAt10"] == 1
    assert metrics["catalogueCoverage"] > 0
    assert {"genreDiversity", "intraListDiversity", "novelty"} <= metrics.keys()
    assert report["counts"]["testInteractions"] == 2
