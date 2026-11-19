"""Polite HTTP fetcher: cache first, rate-limit per host, retry on 429/5xx."""
from __future__ import annotations

import time
from typing import Callable
from urllib.parse import urlsplit

import httpx

from ilfootball.core.ratelimit import HostRateLimiter
from ilfootball.core.raw_store import RawStore

RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(
        self,
        store: RawStore,
        limiter: HostRateLimiter,
        client: httpx.Client,
        max_retries: int = 4,
        backoff_base: float = 5.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = store
        self.limiter = limiter
        self.client = client
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep

    def get(
        self, source: str, entity: str, key: str, url: str, ext: str = "html", refresh: bool = False
    ) -> bytes:
        if not refresh and self.store.exists(source, entity, key, ext):
            return self.store.load(source, entity, key, ext)
        host = urlsplit(url).hostname or ""
        for attempt in range(self.max_retries + 1):
            self.limiter.wait(host)
            try:
                resp = self.client.get(url)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise FetchError(f"{url}: {exc}") from exc
            else:
                if resp.status_code == 200:
                    self.store.save(source, entity, key, ext, resp.content)
                    return resp.content
                if resp.status_code not in RETRY_STATUSES or attempt == self.max_retries:
                    raise FetchError(f"{url}: HTTP {resp.status_code}")
            self._sleep(self.backoff_base * 2**attempt)
        raise AssertionError("unreachable")


def make_client(user_agent: str, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent, "Accept-Language": "he,en;q=0.8"},
        timeout=timeout,
        follow_redirects=True,
    )
