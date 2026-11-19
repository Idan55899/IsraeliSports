import httpx
import pytest

from ilfootball.core.http import FetchError, Fetcher
from ilfootball.core.ratelimit import HostRateLimiter
from ilfootball.core.raw_store import RawStore


def build(tmp_path, handler):
    calls: list[str] = []

    def recording(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return handler(request, len(calls))

    client = httpx.Client(transport=httpx.MockTransport(recording))
    limiter = HostRateLimiter(lambda h: 0.0, jitter=0.0, sleep=lambda s: None)
    fetcher = Fetcher(RawStore(tmp_path), limiter, client, max_retries=2, sleep=lambda s: None)
    return fetcher, calls


def test_fetch_saves_and_second_call_hits_cache(tmp_path):
    fetcher, calls = build(tmp_path, lambda req, n: httpx.Response(200, content=b"ok"))
    assert fetcher.get("ifa", "match", "1", "https://x.test/m/1") == b"ok"
    assert fetcher.get("ifa", "match", "1", "https://x.test/m/1") == b"ok"
    assert len(calls) == 1


def test_refresh_bypasses_cache(tmp_path):
    fetcher, calls = build(tmp_path, lambda req, n: httpx.Response(200, content=f"v{n}".encode()))
    fetcher.get("ifa", "match", "1", "https://x.test/m/1")
    assert fetcher.get("ifa", "match", "1", "https://x.test/m/1", refresh=True) == b"v2"


def test_retries_on_429_then_succeeds(tmp_path):
    def handler(req, n):
        return httpx.Response(429) if n == 1 else httpx.Response(200, content=b"ok")

    fetcher, calls = build(tmp_path, handler)
    assert fetcher.get("ifa", "match", "1", "https://x.test/m/1") == b"ok"
    assert len(calls) == 2


def test_404_fails_fast_and_is_not_cached(tmp_path):
    fetcher, calls = build(tmp_path, lambda req, n: httpx.Response(404))
    with pytest.raises(FetchError, match="404"):
        fetcher.get("ifa", "match", "1", "https://x.test/m/1")
    assert len(calls) == 1
    assert not RawStore(tmp_path).exists("ifa", "match", "1", "html")


def test_gives_up_after_max_retries(tmp_path):
    fetcher, calls = build(tmp_path, lambda req, n: httpx.Response(503))
    with pytest.raises(FetchError, match="503"):
        fetcher.get("ifa", "match", "1", "https://x.test/m/1")
    assert len(calls) == 3
