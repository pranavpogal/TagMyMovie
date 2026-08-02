# TagMyMovie ML service

This directory contains the local Python recommendation service and offline jobs. It currently provides normalized TMDB catalogue ingestion and deterministic feature-text generation. HTTP inference and model jobs are added in later phases.

## Local setup

```bash
cd ml-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

The job reads configuration from the environment and loads `ml-service/.env` when present.

## Build the catalogue

```bash
python -m jobs.build_media_catalog
```

Use `CATALOGUE_SYNC_MODE=incremental` to skip recently synchronized titles, or `full` to refresh every discovered title. Individual source/title failures are counted and logged while processing continues. The command exits non-zero for configuration, MongoDB, or other unrecoverable pipeline failures and prints created, updated, unchanged, and failed counts.

The job is an offline command. It is not run by an HTTP request or service startup.

## Feature text

`app.content.feature_text` converts a normalized catalogue record into stable, labelled text and a SHA-256 feature hash. Movie directors and TV creators are handled separately; missing fields are omitted. Cast and keyword limits can be configured with `FEATURE_TEXT_CAST_LIMIT` and `FEATURE_TEXT_KEYWORD_LIMIT`.

The module also identifies stale embeddings from changes to the feature hash, embedding model/version, vector dimension, or vector values. It does not generate embeddings itself.

## Build content embeddings and index

```bash
python -m jobs.build_content_index
```

The offline command lazily loads the configured sentence-transformer once, embeds stale catalogue records in batches, writes normalized vectors and their model metadata to MongoDB, and atomically replaces a local FAISS inner-product index plus its identity manifest. It retries a failed batch record-by-record so one malformed title does not discard the other items.

Defaults use `sentence-transformers/all-MiniLM-L6-v2`, embedding version `content-embedding-v1`, batches of 64, and artifacts under `artifacts/content`. The model is downloaded by the sentence-transformers library on its first use. Catalogue ingestion must have populated MongoDB first.

## Vector search

`app.content.vector_store` is the backend-neutral contract used by later recommendation phases. Set `VECTOR_BACKEND=faiss` for the local persisted index or `mongodb` for Atlas Vector Search. Both implementations support upsert, search, deletion, health checks, dimension validation, candidate over-fetching, and the same media type, language, genre, release-year, and vote-count filters.

For Atlas, create the search index named by `VECTOR_INDEX_NAME` on `media_catalog.embedding` using `docs/atlas-vector-search-index.json`. Its checked-in definition uses 384 dimensions for the default MiniLM model; change `numDimensions` when selecting a model with a different output size.

## Content-based user profiles

`UserContentProfileBuilder` loads a user’s supported interactions, onboarding seed titles, and current-model catalogue embeddings. It applies the versioned centralized interaction weights and recency decay, caps repeated weak activity, uses only the newest rating/favourite state, subtracts a bounded negative centroid, and returns a normalized profile vector. Users without usable positive evidence receive an explicit `cold_start` result rather than an invalid or zero vector.

Profile behavior is configured with `PROFILE_VERSION`, `RECENCY_DECAY_FACTOR`, `PROFILE_WEAK_POSITIVE_CAP`, and `PROFILE_NEGATIVE_CENTROID_SCALE`.

## Build the collaborative dataset

```bash
python -m jobs.build_interaction_matrix
```

The offline job resolves interactions against existing users and compound catalogue identities, removes invalid/duplicate records, aggregates only positive implicit confidence with decay and saturation, filters users below the configured minimum item count, and writes a SciPy CSR user-item matrix. Generation-specific matrix and mapping files are activated through an atomically replaced manifest, preserving the previous usable dataset if a build fails.

Negative ratings, favourite removals, not-interested events, and pure impressions remain in MongoDB but are not positive ALS entries. They are reserved for later exclusion and ranking logic.

## Train the collaborative model

```bash
python -m jobs.train_collaborative_model
```

The job rebuilds the validated users-by-items dataset, makes a deterministic leave-one-out split, trains `implicit` ALS, generates held-out recommendations, and calculates actual Recall, NDCG, and Hit Rate at the configured K. A candidate is promoted only when factor shapes and values are valid, enough validation users exist, metrics are finite, and recall meets `CF_MIN_RECALL_AT_K`.

Successful versions are safely serialized under `artifacts/collaborative/versions/`; an atomically replaced `current` symlink exposes the active model, mappings, metadata, and evaluation. Failed candidates leave the previous current model untouched.

## Optional MovieLens bootstrap

Download and extract a MovieLens dataset yourself after reviewing its accompanying README and license, then run:

```bash
python -m jobs.bootstrap_movielens --dataset-path /path/to/ml-latest-small
```

The opt-in job reads only local `ratings.csv` and `links.csv`, maps positive ratings to catalogue movie TMDB IDs, namespaces users as `movielens:<id>`, and persists an external bootstrap matrix. No dataset rows are committed to Git.

Training supports `CF_DATA_SOURCE=tagmymovie`, `movielens`, or `combined`; the latter two require `MOVIELENS_DATASET_PATH`. Combined artifacts record source counts and separately report native-user validation when enough native users exist. MovieLens never supplies TV interactions and its metrics are not treated as TagMyMovie production performance.

## Collaborative inference for users outside the model

The collaborative inference layer loads and validates the active ALS model/mappings once per promoted version. It rebuilds a user’s current positive implicit-confidence row against that exact item mapping. Mapped users use their stored factor; unmapped users with at least `CF_MIN_OVERLAP_ITEMS` use `implicit`’s in-memory `recalculate_user` path.

Inference never retrains ALS or writes per-user artifacts. Missing models, insufficient overlap, invalid stored/temporary factors, and recommendation failures return an explicit `content_fallback` result. Raw ALS scores and dynamic collaborative confidence are returned separately.

Collaborative confidence is inactive below three mapped items, then moves through configurable low (3–5), moderate (6–9), and normal (10+) overlap tiers. Within a tier, the weight also reflects meaningful and unique positive activity, interaction freshness, model freshness, catalogue coverage, factor validity, and whether the factor is stored or temporary. The evidence is returned with the result, so the presence of an ALS artifact alone can never activate collaborative scoring.

## Candidate generation

The candidate generator independently requests up to 150 content-profile matches, 150 ALS recommendations, 40 vote-qualified popularity titles, and 40 titles matching explicit genre/language/release-period preferences. A media-detail request can additionally request 150 titles similar to the current compound item. A cold profile or missing seed embedding returns an empty corresponding pool without preventing the other configured pools from contributing.

Pools merge strictly by `mediaType:tmdbId`; movie and TV identifiers cannot collide. Each merged candidate retains ordered `source_models`, source-specific raw scores, normalized scores, and catalogue metadata.

Normalization uses tied rank percentiles independently within each source. Higher scores map toward 1 and lower scores toward 0 without comparing raw cosine, ALS, or popularity scales. Ties share their average rank, an all-equal multi-item pool receives neutral 0.5 scores, a one-item pool receives 1, and missing/invalid source scores remain absent. Normalized scores are still not blended or ranked until Phase 18.

The versioned hybrid ranker now calculates normalized content, collaborative, explicit-preference, quality, popularity, freshness, seed-similarity, negative-penalty, and seen-penalty features. Collaborative weight grows continuously from zero to 0.40 with the Phase 15 confidence; content, preferences, and quality/popularity weights interpolate down so the positive weights always total one. Final ties use the compound item key. Public serialization omits the internal feature breakdown, while diagnostic serialization retains it for tests and troubleshooting.

Before ranking, the versioned feedback policy excludes exact not-interested titles, low ratings, configured existing favourites/ratings, and the current detail-page seed. Removed favourites, recent recommendation clicks, and repeated impressions receive capped penalties. Similarity penalties require repeated dislike evidence for the same genre or person; a single disliked title never rejects a genre. Detail views are not treated as proof of watching.

After hybrid scoring, deterministic MMR diversity re-ranking balances 80% relevance against 20% maximum similarity to selected items. Similarity considers genres, franchises/title series, directors, major cast, release decades, languages, popularity bands, and catalogue embedding cosine when available. It preserves hybrid scores, limits a franchise to two items while alternatives exist, and returns up to 20 recommendations.

Each diversified item receives one to three deterministic explanations drawn only from its real evidence: matched genre/language preferences, current-title similarity, content-profile activity, privacy-safe collaborative provenance, or measured quality/popularity. No LLM is used, and explanations never expose another user's identity, reviews, history, or latent-factor values.

Every recommendation result now carries a versioned strategy selected from the provenance of the final returned items. Seeded, content/collaborative hybrid, content-only, collaborative-only, personalized hybrid, onboarding-preference, cold-start popularity, and TMDB fallback responses are distinguished accurately. Collaborative labels require nonzero collaborative confidence.

## Run the ML API

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

FastAPI exposes `/health`, `/ready`, `/models/status`, `/recommendations/{user_id}`, `/similar/{media_type}/{media_id}`, and `/semantic-search`. Interactive local documentation is available at `/docs`. Debug recommendation output requires both `debug=true` and the private `X-Internal-Key` matching `ML_INTERNAL_DEBUG_KEY`; when no key is configured, debug access is disabled.

## Offline model evaluation

Run the reproducible time-based evaluation and guarded candidate promotion with:

```bash
python -m jobs.evaluate_models
```

The JSON report compares popularity, content-based, collaborative ALS, hybrid without diversity, and hybrid with diversity. It includes Recall, Hit Rate, NDCG, MAP, MRR, catalogue coverage, genre diversity, intra-list diversity, novelty, dataset counts, and cold-start counts. Users below `EVALUATION_MIN_INTERACTIONS_PER_USER` stay in training but are excluded from per-user metrics. Insufficient samples produce a warning and block promotion. A candidate version is written and reloaded before the `current` symlink is atomically changed; failed checks preserve the previous current model. Reports are saved under `artifacts/collaborative/evaluations/`.

## Tests

```bash
pytest
```

Tests use fakes and do not require live TMDB or MongoDB access.
