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

## Tests

```bash
pytest
```

Tests use fakes and do not require live TMDB or MongoDB access.
