from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LOGGER = logging.getLogger(__name__)


class TmdbRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class TmdbSource:
    media_type: str
    name: str
    path: str


TMDB_SOURCES = (
    TmdbSource("movie", "popular", "movie/popular"),
    TmdbSource("movie", "top_rated", "movie/top_rated"),
    TmdbSource("movie", "trending", "trending/movie/week"),
    TmdbSource("movie", "now_playing", "movie/now_playing"),
    TmdbSource("tv", "popular", "tv/popular"),
    TmdbSource("tv", "top_rated", "tv/top_rated"),
    TmdbSource("tv", "trending", "trending/tv/week"),
    TmdbSource("tv", "currently_airing", "tv/on_the_air"),
)


class TmdbClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        access_token: str | None,
        timeout_seconds: float,
        max_retries: int,
        retry_backoff_seconds: float,
        requests_per_second: float,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = f"{base_url.rstrip('/')}/"
        self.api_key = api_key
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.minimum_interval = 1 / requests_per_second
        self.opener = opener
        self.sleeper = sleeper
        self.monotonic = monotonic
        self._last_request_at: float | None = None

    def _rate_limit(self) -> None:
        if self._last_request_at is not None:
            elapsed = self.monotonic() - self._last_request_at
            if elapsed < self.minimum_interval:
                self.sleeper(self.minimum_interval - elapsed)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        if self.api_key and not self.access_token:
            query["api_key"] = self.api_key
        url = f"{self.base_url}{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query)}"

        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._rate_limit()
            self._last_request_at = self.monotonic()
            try:
                with self.opener(
                    Request(url, headers=headers), timeout=self.timeout_seconds
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                last_error = error
                transient = error.code == 429 or 500 <= error.code < 600
                if not transient or attempt >= self.max_retries:
                    break
                retry_after = error.headers.get("Retry-After") if error.headers else None
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.replace(".", "", 1).isdigit()
                    else self.retry_backoff_seconds * (2**attempt)
                )
                self.sleeper(delay)
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                self.sleeper(self.retry_backoff_seconds * (2**attempt))

        raise TmdbRequestError(f"TMDB request failed for {path}") from last_error

    def list_page(self, source: TmdbSource, page: int) -> list[dict[str, Any]]:
        payload = self.get(source.path, {"page": page})
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise TmdbRequestError(f"TMDB returned invalid results for {source.path}")
        return results

    def media_detail(self, media_type: str, tmdb_id: str) -> dict[str, Any]:
        return self.get(
            f"{media_type}/{tmdb_id}",
            {"append_to_response": "credits,keywords"},
        )
