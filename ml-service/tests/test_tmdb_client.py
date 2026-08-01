from __future__ import annotations

import io
from urllib.error import HTTPError

import pytest

from app.catalogue.tmdb_client import TmdbClient, TmdbRequestError, TmdbSource


class Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def client(opener, sleeps: list[float]) -> TmdbClient:
    clock = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    return TmdbClient(
        base_url="https://api.themoviedb.org/3/",
        api_key="key",
        access_token=None,
        timeout_seconds=10,
        max_retries=2,
        retry_backoff_seconds=0.5,
        requests_per_second=100,
        opener=opener,
        sleeper=sleeps.append,
        monotonic=lambda: next(clock),
    )


def test_retries_transient_http_errors_and_preserves_query_parameters() -> None:
    requests = []
    sleeps: list[float] = []

    def opener(request, timeout):
        requests.append((request, timeout))
        if len(requests) == 1:
            raise HTTPError(request.full_url, 503, "unavailable", {}, io.BytesIO())
        return Response(b'{"results":[{"id":603}]}')

    result = client(opener, sleeps).list_page(
        TmdbSource("movie", "popular", "movie/popular"), 2
    )

    assert result == [{"id": 603}]
    assert "page=2" in requests[-1][0].full_url
    assert "api_key=key" in requests[-1][0].full_url
    assert 0.5 in sleeps


def test_does_not_retry_non_transient_client_errors() -> None:
    attempts = 0

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        raise HTTPError(request.full_url, 401, "unauthorized", {}, io.BytesIO())

    with pytest.raises(TmdbRequestError):
        client(opener, []).get("movie/603")
    assert attempts == 1
