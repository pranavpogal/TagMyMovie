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

Inference never retrains ALS or writes per-user artifacts. Missing models, insufficient overlap, invalid temporary factors, and recommendation failures return an explicit `content_fallback` result. Raw ALS scores and preliminary overlap confidence are returned separately.

## Tests

```bash
pytest
```

Tests use fakes and do not require live TMDB or MongoDB access.
