from __future__ import annotations

from bson import ObjectId

from app.recommendations.repository import CandidateRepository, _release_year_ranges


class Cursor(list):
    def __init__(self, documents):
        super().__init__(documents)
        self.sort_value = None
        self.limit_value = None

    def sort(self, value):
        self.sort_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return Cursor(self[:value])


class Collection:
    def __init__(self, documents=(), one=None):
        self.documents = list(documents)
        self.one = one
        self.find_calls = []
        self.find_one_calls = []

    def find(self, query, projection):
        self.find_calls.append((query, projection))
        return Cursor(self.documents)

    def find_one(self, query, projection):
        self.find_one_calls.append((query, projection))
        return self.one


class Database:
    def __init__(self, catalogue, preferences):
        self.values = {"media_catalog": catalogue, "userpreferences": preferences}

    def __getitem__(self, key):
        return self.values[key]


def test_popularity_applies_vote_quality_constraints_and_limit() -> None:
    catalogue = Collection(
        [{"mediaType": "movie", "tmdbId": "1"}, {"mediaType": "tv", "tmdbId": "2"}]
    )
    repository = CandidateRepository(Database(catalogue, Collection()))

    assert len(repository.popularity_candidates(
        limit=1, minimum_vote_count=100, minimum_vote_average=6.5
    )) == 1
    query = catalogue.find_calls[0][0]
    assert query["voteCount"] == {"$gte": 100}
    assert query["voteAverage"] == {"$gte": 6.5}


def test_preferences_require_explicit_filters_and_combine_them() -> None:
    user_id = ObjectId()
    catalogue = Collection([{"mediaType": "movie", "tmdbId": "1"}])
    preferences = Collection(one={
        "preferredGenreIds": [18],
        "preferredLanguages": ["en"],
        "preferredReleasePeriods": ["1990s", "2020-present"],
    })
    repository = CandidateRepository(Database(catalogue, preferences))

    result = repository.preference_candidates(str(user_id), limit=40)

    assert len(result) == 1
    clauses = catalogue.find_calls[0][0]["$and"]
    assert {"genreIds": {"$in": [18]}} in clauses
    assert {"originalLanguage": {"$in": ["en"]}} in clauses
    assert {"$or": [{"releaseYear": {"$gte": 1990, "$lte": 1999}},
                    {"releaseYear": {"$gte": 2020}}]} in clauses


def test_no_explicit_preferences_returns_no_candidates_without_catalogue_scan() -> None:
    catalogue = Collection()
    repository = CandidateRepository(Database(catalogue, Collection(one={})))

    assert repository.preference_candidates(ObjectId(), limit=40) == []
    assert catalogue.find_calls == []


def test_seed_embedding_uses_compound_identity_and_release_parser_is_bounded() -> None:
    catalogue = Collection(one={"embedding": [1.0, 0.0]})
    repository = CandidateRepository(Database(catalogue, Collection()))

    assert repository.item_embedding("tv:42") == [1.0, 0.0]
    assert catalogue.find_one_calls[0][0]["mediaType"] == "tv"
    assert catalogue.find_one_calls[0][0]["tmdbId"] == "42"
    assert repository.item_embedding("invalid") is None
    assert _release_year_ranges(["classic", "bad", "2000_2005"]) == [
        {"$lte": 1979}, {"$gte": 2000, "$lte": 2005}
    ]


def test_ranking_context_loads_normalized_explicit_preferences() -> None:
    user_id = ObjectId()
    preferences = Collection(one={
        "preferredGenreIds": [18, 28],
        "preferredLanguages": ["EN"],
        "preferredReleasePeriods": ["1990s", "recent"],
    })
    repository = CandidateRepository(Database(Collection(), preferences))

    context = repository.ranking_context(user_id)

    assert context.preferred_genre_ids == {18, 28}
    assert context.preferred_languages == {"en"}
    assert context.preferred_release_periods == ((1990, 1999), (2020, None))


def test_media_metadata_hydrates_compound_search_results() -> None:
    catalogue = Collection([
        {"mediaType": "movie", "tmdbId": "42", "title": "Mystery", "posterPath": "/p.jpg"},
        {"mediaType": "tv", "tmdbId": "42", "title": "Series", "posterPath": "/tv.jpg"},
    ])
    repository = CandidateRepository(Database(catalogue, Collection()))

    metadata = repository.media_metadata(["movie:42", "tv:42", "invalid"])

    assert metadata["movie:42"]["title"] == "Mystery"
    assert metadata["tv:42"]["posterPath"] == "/tv.jpg"
    identities = catalogue.find_calls[0][0]["$or"]
    assert {"mediaType": "movie", "tmdbId": "42"} in identities
