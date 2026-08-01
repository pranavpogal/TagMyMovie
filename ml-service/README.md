# TagMyMovie ML service

This directory contains the local Python recommendation service and offline jobs. Phase 6 provides the normalized TMDB catalogue-ingestion job; HTTP inference and model jobs are added in later phases.

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

## Tests

```bash
pytest
```

Tests use fakes and do not require live TMDB or MongoDB access.
