# Plan 1 — Pipeline Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the source-agnostic core of the Israeli football dataset pipeline: config, a cached and polite HTTP fetcher, the canonical DuckDB schema, typed rows with upsert, cross-source id resolution, data-quality checks and a CLI. Then use it to capture real pages from every candidate source.

**Architecture:** One Python package `ilfootball` (src layout). Data moves fetch → raw gzip cache → parse → typed rows → DuckDB. Everything in this plan is independent of any source. Source adapters plug in later under `src/ilfootball/sources/<name>/` (Plan 2+). Design: `docs/superpowers/specs/2026-11-19-israeli-football-dataset-design.md`.

**Tech Stack:** Python ≥ 3.12, `uv`, `httpx`, `duckdb`, `pydantic` v2, `rapidfuzz`, `pytest`.

## Global Constraints

- Free sources and free tooling only. No paid APIs or services.
- No network access in tests. Use `httpx.MockTransport` and fake clocks.
- Every HTTP response is cached before it's used. Responses are only saved on HTTP 200.
- Politeness: at least 1 s between requests per host (defaults in `config.py`, 3–6 s for scraped sites). No proxy rotation or block evasion.
- Canonical ids are TEXT `<prefix>-<source>-<source_id>` (e.g. `pl-ifa-4411`).
- Model field names must equal column names in `schema.sql`.
- `data/` is never committed.
- Run all commands from the repository root. The test command is `uv run pytest`.

## File map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, `ilfootball` console script, pytest config |
| `src/ilfootball/config.py` | `Settings`, `load_settings()` |
| `src/ilfootball/core/raw_store.py` | `RawStore` gzip cache |
| `src/ilfootball/core/ratelimit.py` | `HostRateLimiter` |
| `src/ilfootball/core/http.py` | `Fetcher`, `FetchError`, `make_client()` |
| `src/ilfootball/resolve/normalize.py` | `normalize_name()`, `name_key()` |
| `src/ilfootball/db/schema.sql` | Canonical tables |
| `src/ilfootball/db/connect.py` | `init_db()` |
| `src/ilfootball/models.py` | Pydantic row models |
| `src/ilfootball/load/upsert.py` | `upsert()` |
| `src/ilfootball/resolve/id_map.py` | `IdMap`, `Candidate` |
| `src/ilfootball/quality/checks.py` | `Issue`, checks, `run_all()` |
| `src/ilfootball/cli.py` | `main()` with `init-db`, `check`, `fetch` |
| `docs/source-findings.md` | Spike results per source (Task 11) |
| `tests/fixtures/<source>/` | Saved real pages for parser tests (Task 11) |

---
### Task 1: Project scaffold and settings

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/ilfootball/__init__.py` and the empty `__init__.py` of each subpackage
- Create: `src/ilfootball/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Settings(data_dir: Path, user_agent: str, default_interval: float, host_intervals: dict[str, float])` with properties `raw_dir: Path` and `db_path: Path` and method `interval_for(host: str) -> float`; `load_settings() -> Settings` reads `ILF_DATA_DIR` (default `data`) and `ILF_USER_AGENT`.

- [ ] **Step 1: Create the project files**

Create `pyproject.toml`:

```toml
[project]
name = "ilfootball"
version = "0.1.0"
description = "Israeli football dataset pipeline"
requires-python = ">=3.12"
dependencies = [
  "duckdb>=1.1",
  "httpx>=0.27",
  "pydantic>=2.7",
  "rapidfuzz>=3.9",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
ilfootball = "ilfootball.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ilfootball"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `.gitignore`:

```
data/
.venv/
__pycache__/
.pytest_cache/
*.duckdb
*.duckdb.wal
```

Create the empty package markers:

```bash
mkdir -p src/ilfootball/core src/ilfootball/db src/ilfootball/resolve src/ilfootball/load src/ilfootball/quality tests
touch src/ilfootball/__init__.py src/ilfootball/core/__init__.py src/ilfootball/db/__init__.py \
      src/ilfootball/resolve/__init__.py src/ilfootball/load/__init__.py src/ilfootball/quality/__init__.py
uv sync --extra dev
```

Expected: `uv` creates `.venv/` and `uv.lock` with no errors.

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:

```python
from pathlib import Path

from ilfootball.config import Settings, load_settings


def test_load_settings_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    s = load_settings()
    assert s.data_dir == tmp_path
    assert s.raw_dir == tmp_path / "raw"
    assert s.db_path == tmp_path / "ilfootball.duckdb"


def test_interval_for_known_and_unknown_host():
    s = Settings(data_dir=Path("data"))
    assert s.interval_for("www.transfermarkt.com") == 6.0
    assert s.interval_for("example.org") == 5.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.config'`

- [ ] **Step 4: Write minimal implementation**

`src/ilfootball/config.py`:

```python
"""Runtime settings, read from environment variables with safe defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_AGENT = "ilfootball-dataset/0.1 (personal research project)"

# Minimum seconds between requests to the same host.
DEFAULT_HOST_INTERVALS: dict[str, float] = {
    "www.football.org.il": 3.0,
    "www.transfermarkt.com": 6.0,
    "www.sofascore.com": 4.0,
    "www.fotmob.com": 4.0,
    "query.wikidata.org": 1.0,
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    user_agent: str = DEFAULT_USER_AGENT
    default_interval: float = 5.0
    host_intervals: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_HOST_INTERVALS))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ilfootball.duckdb"

    def interval_for(self, host: str) -> float:
        return self.host_intervals.get(host, self.default_interval)


def load_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("ILF_DATA_DIR", "data")),
        user_agent=os.environ.get("ILF_USER_AGENT", DEFAULT_USER_AGENT),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore src tests/test_config.py
git commit -m "feat: project scaffold and settings"
```

---

### Task 2: Raw response store

**Files:**
- Create: `src/ilfootball/core/raw_store.py`
- Test: `tests/test_raw_store.py`

**Interfaces:**
- Consumes: nothing
- Produces: `RawStore(base: Path)` with `path_for(source, entity, key, ext) -> Path`, `exists(...) -> bool`, `save(source, entity, key, ext, content: bytes) -> Path`, `load(...) -> bytes`. All four take the same `(source: str, entity: str, key: str, ext: str)` arguments. Files live at `base/<source>/<entity>/<key>.<ext>.gz` with unsafe characters replaced by `_`. `ValueError` is raised if a part is empty after sanitising.

- [ ] **Step 1: Write the failing test**

`tests/test_raw_store.py`:

```python
import pytest

from ilfootball.core.raw_store import RawStore


def test_save_then_load_roundtrip(tmp_path):
    store = RawStore(tmp_path)
    path = store.save("ifa", "match", "12345", "html", "<p>שלום</p>".encode())
    assert path == tmp_path / "ifa" / "match" / "12345.html.gz"
    assert store.exists("ifa", "match", "12345", "html")
    assert store.load("ifa", "match", "12345", "html").decode() == "<p>שלום</p>"


def test_keys_are_sanitised(tmp_path):
    store = RawStore(tmp_path)
    path = store.path_for("ifa", "match", "season=2025/26&id=7", "html")
    assert path.name == "season_2025_26_id_7.html.gz"


def test_empty_key_rejected(tmp_path):
    with pytest.raises(ValueError):
        RawStore(tmp_path).path_for("ifa", "match", "///", "html")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_raw_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.core.raw_store'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/core/raw_store.py`:

```python
"""Immutable, gzip-compressed cache of every downloaded response."""
from __future__ import annotations

import gzip
import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(part: str) -> str:
    cleaned = _SAFE.sub("_", part).strip("._")
    if not cleaned:
        raise ValueError(f"unusable path part: {part!r}")
    return cleaned


class RawStore:
    def __init__(self, base: Path) -> None:
        self.base = Path(base)

    def path_for(self, source: str, entity: str, key: str, ext: str) -> Path:
        return self.base / _safe(source) / _safe(entity) / f"{_safe(key)}.{_safe(ext)}.gz"

    def exists(self, source: str, entity: str, key: str, ext: str) -> bool:
        return self.path_for(source, entity, key, ext).exists()

    def save(self, source: str, entity: str, key: str, ext: str, content: bytes) -> Path:
        path = self.path_for(source, entity, key, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(gzip.compress(content))
        tmp.replace(path)
        return path

    def load(self, source: str, entity: str, key: str, ext: str) -> bytes:
        return gzip.decompress(self.path_for(source, entity, key, ext).read_bytes())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_raw_store.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/core/raw_store.py tests/test_raw_store.py
git commit -m "feat: gzip raw response store"
```

---

### Task 3: Per-host rate limiter

**Files:**
- Create: `src/ilfootball/core/ratelimit.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Consumes: `Settings.interval_for` (Task 1) is the usual `interval_for` argument
- Produces: `HostRateLimiter(interval_for: Callable[[str], float], jitter=0.5, clock=time.monotonic, sleep=time.sleep, rand=random.random)` with `wait(host: str) -> float`, which returns the seconds slept.

- [ ] **Step 1: Write the failing test**

`tests/test_ratelimit.py`:

```python
from ilfootball.core.ratelimit import HostRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(clock: FakeClock) -> HostRateLimiter:
    return HostRateLimiter(lambda host: 3.0, jitter=0.0, clock=clock.time, sleep=clock.sleep)


def test_first_request_does_not_wait():
    clock = FakeClock()
    assert make(clock).wait("a.com") == 0.0
    assert clock.sleeps == []


def test_second_request_waits_remaining_interval():
    clock = FakeClock()
    limiter = make(clock)
    limiter.wait("a.com")
    clock.now += 1.0
    assert limiter.wait("a.com") == 2.0


def test_hosts_are_independent():
    clock = FakeClock()
    limiter = make(clock)
    limiter.wait("a.com")
    assert limiter.wait("b.com") == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ratelimit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.core.ratelimit'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/core/ratelimit.py`:

```python
"""Per-host politeness delay: at least `interval` seconds (+ jitter) between requests."""
from __future__ import annotations

import random
import time
from typing import Callable


class HostRateLimiter:
    def __init__(
        self,
        interval_for: Callable[[str], float],
        jitter: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._interval_for = interval_for
        self._jitter = jitter
        self._clock = clock
        self._sleep = sleep
        self._rand = rand
        self._last: dict[str, float] = {}

    def wait(self, host: str) -> float:
        """Block until `host` may be requested again. Returns seconds slept."""
        slept = 0.0
        last = self._last.get(host)
        if last is not None:
            due = last + self._interval_for(host) + self._jitter * self._rand()
            slept = max(0.0, due - self._clock())
            if slept > 0:
                self._sleep(slept)
        self._last[host] = self._clock()
        return slept
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ratelimit.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/core/ratelimit.py tests/test_ratelimit.py
git commit -m "feat: per-host rate limiter"
```

---

### Task 4: Polite HTTP fetcher

**Files:**
- Create: `src/ilfootball/core/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Consumes: `RawStore` (Task 2), `HostRateLimiter` (Task 3)
- Produces: `Fetcher(store, limiter, client: httpx.Client, max_retries=4, backoff_base=5.0, sleep=time.sleep)` with `get(source, entity, key, url, ext='html', refresh=False) -> bytes`; `FetchError(RuntimeError)`; `make_client(user_agent: str, timeout=30.0) -> httpx.Client`. Statuses 429/500/502/503/504 and transport errors are retried with backoff `backoff_base * 2**attempt`. Other non-200 statuses raise immediately. Only a 200 response is saved.

- [ ] **Step 1: Write the failing test**

`tests/test_http.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_http.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.core.http'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/core/http.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_http.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/core/http.py tests/test_http.py
git commit -m "feat: cache-first polite HTTP fetcher"
```

---

### Task 5: Hebrew/Latin name normalisation

**Files:**
- Create: `src/ilfootball/resolve/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: nothing
- Produces: `normalize_name(name: str) -> str` (lowercase; accents, niqqud, geresh/gershayim and quotes stripped; Hebrew final letters mapped to their regular forms ך→כ ם→מ ן→נ ף→פ ץ→צ; separators `-_/,()` turned into spaces), and `name_key(name: str) -> str`, which sorts the tokens so word order doesn't matter.

- [ ] **Step 1: Write the failing test**

`tests/test_normalize.py`:

```python
import pytest

from ilfootball.resolve.normalize import name_key, normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Eran Zahavi", "eran zahavi"),
        ("  ERAN   ZAHAVI ", "eran zahavi"),
        ("Dor Peretz-Levi", "dor peretz levi"),
        ("Mu'nas Dabbur", "munas dabbur"),
        ("Bnei Sakhnin F.C.", "bnei sakhnin fc"),
        ("José Ramírez", "jose ramirez"),
        ("עֵרָן זְהָבִי", "ערנ זהבי"),
        ("מכבי ת״א", "מכבי תא"),
        ("הפועל ב׳׳ש", "הפועל בש"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_name_key_is_order_insensitive():
    assert name_key("Zahavi Eran") == name_key("Eran Zahavi") == "eran zahavi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.resolve.normalize'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/resolve/normalize.py`:

```python
"""Name normalisation for matching the same person/club across sources."""
from __future__ import annotations

import re
import unicodedata

_NIQQUD = re.compile(r"[֑-ׇ]")
_FINAL_LETTERS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_DROP = re.compile(r"[׳״'\"`’‘”“.]")
_SEPARATORS = re.compile(r"[-_/,()]+")
_SPACES = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase, strip accents/niqqud/punctuation, unify Hebrew final letters."""
    text = _NIQQUD.sub("", name)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.translate(_FINAL_LETTERS)
    text = _DROP.sub("", text)
    text = _SEPARATORS.sub(" ", text)
    return _SPACES.sub(" ", text).strip().lower()


def name_key(name: str) -> str:
    """Order-insensitive key: 'Zahavi Eran' and 'Eran Zahavi' give the same key."""
    return " ".join(sorted(normalize_name(name).split()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_normalize.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/resolve/normalize.py tests/test_normalize.py
git commit -m "feat: Hebrew/Latin name normalisation"
```

---

### Task 6: Canonical DuckDB schema

**Files:**
- Create: `src/ilfootball/db/schema.sql`
- Create: `src/ilfootball/db/connect.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: nothing
- Produces: the tables `competition, season, club, player, match, lineup, event, standing, id_map` (exact columns in `schema.sql` below), and `init_db(path: Path | str) -> duckdb.DuckDBPyConnection`, which accepts `":memory:"`, creates parent dirs and can safely run more than once.

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:

```python
from ilfootball.db.connect import init_db

EXPECTED = {"competition", "season", "club", "player", "match", "lineup", "event", "standing", "id_map"}


def tables(con):
    return {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}


def test_init_db_creates_all_tables(tmp_path):
    con = init_db(tmp_path / "sub" / "t.duckdb")
    assert EXPECTED <= tables(con)


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "t.duckdb"
    init_db(path).close()
    con = init_db(path)
    assert EXPECTED <= tables(con)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.db.connect'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/db/schema.sql`:

```sql
-- Canonical ("gold") schema. Ids are TEXT minted by ilfootball.resolve.id_map.
CREATE TABLE IF NOT EXISTS competition (
    competition_id TEXT PRIMARY KEY,
    name_en TEXT,
    name_he TEXT,
    tier INTEGER,
    type TEXT NOT NULL CHECK (type IN ('league', 'cup', 'europe', 'friendly'))
);

CREATE TABLE IF NOT EXISTS season (
    season_id TEXT PRIMARY KEY,
    competition_id TEXT NOT NULL,
    label TEXT NOT NULL,
    start_date DATE,
    end_date DATE
);

CREATE TABLE IF NOT EXISTS club (
    club_id TEXT PRIMARY KEY,
    name_en TEXT,
    name_he TEXT,
    city TEXT,
    founded INTEGER,
    wikidata_qid TEXT
);

CREATE TABLE IF NOT EXISTS player (
    player_id TEXT PRIMARY KEY,
    name_en TEXT,
    name_he TEXT,
    birth_date DATE,
    nationality TEXT,
    position TEXT,
    wikidata_qid TEXT
);

CREATE TABLE IF NOT EXISTS match (
    match_id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL,
    round TEXT,
    stage TEXT,
    kickoff_utc TIMESTAMP,
    home_club_id TEXT NOT NULL,
    away_club_id TEXT NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    stadium TEXT,
    referee TEXT,
    attendance INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'played', 'postponed', 'cancelled', 'awarded'))
);

CREATE TABLE IF NOT EXISTS lineup (
    match_id TEXT NOT NULL,
    club_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    shirt_no INTEGER,
    is_starter BOOLEAN NOT NULL,
    minutes INTEGER,
    is_captain BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (match_id, player_id)
);

-- club_id is always the club of player_id; an own_goal is credited to the opponent.
CREATE TABLE IF NOT EXISTS event (
    event_id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    minute INTEGER NOT NULL,
    added_time INTEGER,
    club_id TEXT NOT NULL,
    player_id TEXT,
    type TEXT NOT NULL CHECK (type IN (
        'goal', 'pen_goal', 'own_goal', 'pen_miss',
        'yellow', 'second_yellow', 'red', 'sub_in', 'sub_out')),
    related_player_id TEXT
);

CREATE TABLE IF NOT EXISTS standing (
    season_id TEXT NOT NULL,
    round INTEGER NOT NULL,
    club_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    played INTEGER, won INTEGER, drawn INTEGER, lost INTEGER,
    goals_for INTEGER, goals_against INTEGER, points INTEGER,
    PRIMARY KEY (season_id, round, club_id)
);

CREATE TABLE IF NOT EXISTS id_map (
    entity_type TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    source_name TEXT,
    confidence DOUBLE NOT NULL,
    method TEXT NOT NULL,
    PRIMARY KEY (entity_type, source, source_id)
);
```

`src/ilfootball/db/connect.py`:

```python
"""Open the DuckDB database and make sure the canonical schema exists."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import duckdb


def init_db(path: Path | str) -> duckdb.DuckDBPyConnection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(files("ilfootball.db").joinpath("schema.sql").read_text(encoding="utf-8"))
    return con
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/db tests/test_db.py
git commit -m "feat: canonical DuckDB schema"
```

---

### Task 7: Row models and upsert

**Files:**
- Create: `src/ilfootball/models.py`
- Create: `src/ilfootball/load/upsert.py`
- Test: `tests/test_upsert.py`

**Interfaces:**
- Consumes: `init_db` (Task 6)
- Produces: frozen pydantic models `Competition, Season, Club, Player, Match, LineupEntry, MatchEvent, Standing`, each with `ClassVar table`. Field names are exactly the column names. `upsert(con, rows: Iterable[Row]) -> int` runs `INSERT OR REPLACE`, grouped by model, and returns the number of rows written.

- [ ] **Step 1: Write the failing test**

`tests/test_upsert.py`:

```python
from datetime import date

from ilfootball.db.connect import init_db
from ilfootball.load.upsert import upsert
from ilfootball.models import Club, Match, Player


def test_upsert_inserts_mixed_rows():
    con = init_db(":memory:")
    n = upsert(con, [
        Club(club_id="cl-1", name_en="Maccabi Haifa"),
        Club(club_id="cl-2", name_en="Hapoel Beer Sheva"),
        Player(player_id="pl-1", name_en="Dor Peretz", birth_date=date(1995, 5, 17)),
    ])
    assert n == 3
    assert con.execute("SELECT count(*) FROM club").fetchone()[0] == 2
    assert con.execute("SELECT birth_date FROM player").fetchone()[0] == date(1995, 5, 17)


def test_upsert_replaces_on_primary_key():
    con = init_db(":memory:")
    m = dict(match_id="ma-1", season_id="se-1", home_club_id="cl-1", away_club_id="cl-2")
    upsert(con, [Match(**m)])
    upsert(con, [Match(**m, home_goals=2, away_goals=1, status="played")])
    assert con.execute("SELECT home_goals, away_goals, status FROM match").fetchall() == [(2, 1, "played")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_upsert.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.load.upsert'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/models.py`:

```python
"""Typed rows for the canonical tables. Field names == column names in schema.sql."""
from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict


class Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    table: ClassVar[str]


class Competition(Row):
    table: ClassVar[str] = "competition"
    competition_id: str
    name_en: str | None = None
    name_he: str | None = None
    tier: int | None = None
    type: Literal["league", "cup", "europe", "friendly"]


class Season(Row):
    table: ClassVar[str] = "season"
    season_id: str
    competition_id: str
    label: str
    start_date: date | None = None
    end_date: date | None = None


class Club(Row):
    table: ClassVar[str] = "club"
    club_id: str
    name_en: str | None = None
    name_he: str | None = None
    city: str | None = None
    founded: int | None = None
    wikidata_qid: str | None = None


class Player(Row):
    table: ClassVar[str] = "player"
    player_id: str
    name_en: str | None = None
    name_he: str | None = None
    birth_date: date | None = None
    nationality: str | None = None
    position: str | None = None
    wikidata_qid: str | None = None


class Match(Row):
    table: ClassVar[str] = "match"
    match_id: str
    season_id: str
    round: str | None = None
    stage: str | None = None
    kickoff_utc: datetime | None = None
    home_club_id: str
    away_club_id: str
    home_goals: int | None = None
    away_goals: int | None = None
    stadium: str | None = None
    referee: str | None = None
    attendance: int | None = None
    status: Literal["scheduled", "played", "postponed", "cancelled", "awarded"] = "scheduled"


class LineupEntry(Row):
    table: ClassVar[str] = "lineup"
    match_id: str
    club_id: str
    player_id: str
    shirt_no: int | None = None
    is_starter: bool
    minutes: int | None = None
    is_captain: bool = False


class MatchEvent(Row):
    table: ClassVar[str] = "event"
    event_id: str
    match_id: str
    minute: int
    added_time: int | None = None
    club_id: str
    player_id: str | None = None
    type: Literal[
        "goal", "pen_goal", "own_goal", "pen_miss",
        "yellow", "second_yellow", "red", "sub_in", "sub_out",
    ]
    related_player_id: str | None = None


class Standing(Row):
    table: ClassVar[str] = "standing"
    season_id: str
    round: int
    club_id: str
    position: int
    played: int | None = None
    won: int | None = None
    drawn: int | None = None
    lost: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    points: int | None = None
```

`src/ilfootball/load/upsert.py`:

```python
"""Write typed rows into DuckDB, replacing rows that have the same primary key."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import duckdb

from ilfootball.models import Row


def upsert(con: duckdb.DuckDBPyConnection, rows: Iterable[Row]) -> int:
    by_table: dict[type[Row], list[Row]] = defaultdict(list)
    for row in rows:
        by_table[type(row)].append(row)
    written = 0
    for model, items in by_table.items():
        cols = list(model.model_fields)
        sql = (
            f"INSERT OR REPLACE INTO {model.table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})"
        )
        con.executemany(sql, [[getattr(r, c) for c in cols] for r in items])
        written += len(items)
    return written
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_upsert.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/models.py src/ilfootball/load/upsert.py tests/test_upsert.py
git commit -m "feat: typed row models and upsert"
```

---

### Task 8: ID map and player resolution

**Files:**
- Create: `src/ilfootball/resolve/id_map.py`
- Test: `tests/test_id_map.py`

**Interfaces:**
- Consumes: `init_db` (Task 6), `name_key` (Task 5)
- Produces: `Candidate(canonical_id: str, name: str, birth_date: date | None = None)`; `IdMap(con)` with `lookup(entity_type, source, source_id) -> str | None`, `register(entity_type, source, source_id, canonical_id, source_name=None, confidence=1.0, method='manual')`, `mint(entity_type, source, source_id, source_name=None) -> str` (returns `f"{PREFIX[entity_type]}-{source}-{source_id}"`), and `resolve_player(source, source_id, name, birth_date, candidates) -> str`. Matches need the same DOB and a `token_sort_ratio` of at least `FUZZY_THRESHOLD = 90.0`. Otherwise a new id is minted. The `method` column records `minted`, `exact_dob_name`, `fuzzy_dob_name` or `manual`.

- [ ] **Step 1: Write the failing test**

`tests/test_id_map.py`:

```python
from datetime import date

from ilfootball.db.connect import init_db
from ilfootball.resolve.id_map import Candidate, IdMap

DOB = date(1987, 7, 25)


def make() -> IdMap:
    return IdMap(init_db(":memory:"))


def test_mint_and_lookup():
    ids = make()
    cid = ids.mint("player", "ifa", "4411", "ערן זהבי")
    assert cid == "pl-ifa-4411"
    assert ids.lookup("player", "ifa", "4411") == cid
    assert ids.lookup("player", "tm", "4411") is None


def test_resolve_known_source_id_returns_existing():
    ids = make()
    ids.register("player", "tm", "57370", "pl-ifa-4411")
    assert ids.resolve_player("tm", "57370", "anything", None, []) == "pl-ifa-4411"


def test_resolve_matches_reordered_name_with_same_dob():
    ids = make()
    cands = [Candidate("pl-ifa-4411", "Eran Zahavi", DOB)]
    assert ids.resolve_player("tm", "57370", "Zahavi Eran", DOB, cands) == "pl-ifa-4411"
    row = ids.con.execute("SELECT method, confidence FROM id_map WHERE source='tm'").fetchone()
    assert row == ("exact_dob_name", 1.0)


def test_resolve_fuzzy_spelling_with_same_dob():
    ids = make()
    cands = [Candidate("pl-ifa-4411", "Eran Zahavi", DOB)]
    assert ids.resolve_player("sofa", "9", "Eran Zehavi", DOB, cands) == "pl-ifa-4411"


def test_resolve_does_not_match_without_dob():
    ids = make()
    cands = [Candidate("pl-ifa-4411", "Eran Zahavi", DOB)]
    assert ids.resolve_player("sofa", "9", "Eran Zahavi", None, cands) == "pl-sofa-9"


def test_resolve_different_dob_mints_new_player():
    ids = make()
    cands = [Candidate("pl-ifa-4411", "Eran Zahavi", DOB)]
    assert ids.resolve_player("tm", "1", "Eran Zahavi", date(2001, 1, 1), cands) == "pl-tm-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_id_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.resolve.id_map'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/resolve/id_map.py`:

```python
"""Map each source's ids to one canonical id per real-world entity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
from rapidfuzz import fuzz

from ilfootball.resolve.normalize import name_key

PREFIX = {"player": "pl", "club": "cl", "match": "ma", "competition": "co", "season": "se", "coach": "ch"}
FUZZY_THRESHOLD = 90.0


@dataclass(frozen=True)
class Candidate:
    canonical_id: str
    name: str
    birth_date: date | None = None


class IdMap:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con

    def lookup(self, entity_type: str, source: str, source_id: str) -> str | None:
        row = self.con.execute(
            "SELECT canonical_id FROM id_map WHERE entity_type=? AND source=? AND source_id=?",
            [entity_type, source, source_id],
        ).fetchone()
        return row[0] if row else None

    def register(
        self, entity_type: str, source: str, source_id: str, canonical_id: str,
        source_name: str | None = None, confidence: float = 1.0, method: str = "manual",
    ) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO id_map VALUES (?, ?, ?, ?, ?, ?, ?)",
            [entity_type, source, source_id, canonical_id, source_name, confidence, method],
        )

    def mint(self, entity_type: str, source: str, source_id: str, source_name: str | None = None) -> str:
        """Create a new canonical id, derived from the first source that saw the entity."""
        canonical_id = f"{PREFIX[entity_type]}-{source}-{source_id}"
        self.register(entity_type, source, source_id, canonical_id, source_name, 1.0, "minted")
        return canonical_id

    def resolve_player(
        self, source: str, source_id: str, name: str, birth_date: date | None,
        candidates: list[Candidate],
    ) -> str:
        """Known id -> exact DOB+name -> fuzzy name (+DOB) -> mint a new player."""
        known = self.lookup("player", source, source_id)
        if known:
            return known
        key = name_key(name)
        best: tuple[float, Candidate] | None = None
        for cand in candidates:
            if birth_date and cand.birth_date and birth_date != cand.birth_date:
                continue
            score = fuzz.token_sort_ratio(key, name_key(cand.name))
            if best is None or score > best[0]:
                best = (score, cand)
        if best:
            score, cand = best
            same_dob = birth_date is not None and birth_date == cand.birth_date
            if score == 100.0 and same_dob:
                self.register("player", source, source_id, cand.canonical_id, name, 1.0, "exact_dob_name")
                return cand.canonical_id
            if score >= FUZZY_THRESHOLD and same_dob:
                self.register("player", source, source_id, cand.canonical_id, name, score / 100, "fuzzy_dob_name")
                return cand.canonical_id
        return self.mint("player", source, source_id, name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_id_map.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/resolve/id_map.py tests/test_id_map.py
git commit -m "feat: cross-source id map and player resolution"
```

---

### Task 9: Data-quality checks

**Files:**
- Create: `src/ilfootball/quality/checks.py`
- Test: `tests/test_quality.py`

**Interfaces:**
- Consumes: `init_db` (Task 6), models and `upsert` (Task 7)
- Produces: `Issue(check: str, match_id: str, detail: str)`; `check_score_matches_events(con) -> list[Issue]` (only for played matches that have events; `own_goal` counts for the opponent); `check_eleven_starters(con) -> list[Issue]`; `ALL_CHECKS`; `run_all(con) -> list[Issue]`.

- [ ] **Step 1: Write the failing test**

`tests/test_quality.py`:

```python
from ilfootball.db.connect import init_db
from ilfootball.load.upsert import upsert
from ilfootball.models import LineupEntry, Match, MatchEvent
from ilfootball.quality.checks import check_eleven_starters, check_score_matches_events, run_all


def played(home_goals, away_goals):
    return Match(match_id="ma-1", season_id="se-1", home_club_id="H", away_club_id="A",
                 home_goals=home_goals, away_goals=away_goals, status="played")


def ev(i, club, kind):
    return MatchEvent(event_id=f"ev-{i}", match_id="ma-1", minute=10 * i, club_id=club, type=kind)


def test_score_consistent_with_goals_and_own_goal():
    con = init_db(":memory:")
    # 2-1: home goal, home penalty, own goal by a home player (counts for away)
    upsert(con, [played(2, 1), ev(1, "H", "goal"), ev(2, "H", "pen_goal"), ev(3, "H", "own_goal"),
                 ev(4, "A", "yellow")])
    assert check_score_matches_events(con) == []


def test_score_mismatch_reported():
    con = init_db(":memory:")
    upsert(con, [played(3, 0), ev(1, "H", "goal")])
    issues = check_score_matches_events(con)
    assert len(issues) == 1
    assert issues[0].detail == "score 3-0 but events give 1-0"


def test_matches_without_events_are_skipped():
    con = init_db(":memory:")
    upsert(con, [played(3, 0)])
    assert check_score_matches_events(con) == []


def test_eleven_starters():
    con = init_db(":memory:")
    rows = [LineupEntry(match_id="ma-1", club_id="H", player_id=f"p{i}", is_starter=True) for i in range(11)]
    rows += [LineupEntry(match_id="ma-1", club_id="A", player_id=f"q{i}", is_starter=i < 10) for i in range(12)]
    upsert(con, rows)
    issues = check_eleven_starters(con)
    assert [(i.match_id, i.detail) for i in issues] == [("ma-1", "club A has 10 starters")]
    assert run_all(con) == issues
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_quality.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.quality.checks'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/quality/checks.py`:

```python
"""Data-quality checks over the canonical tables. Each returns a list of Issues."""
from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Issue:
    check: str
    match_id: str
    detail: str


_SCORE_SQL = """
WITH goals AS (
    SELECT e.match_id,
        SUM(CASE WHEN (e.type IN ('goal','pen_goal') AND e.club_id = m.home_club_id)
                   OR (e.type = 'own_goal' AND e.club_id = m.away_club_id) THEN 1 ELSE 0 END) AS home,
        SUM(CASE WHEN (e.type IN ('goal','pen_goal') AND e.club_id = m.away_club_id)
                   OR (e.type = 'own_goal' AND e.club_id = m.home_club_id) THEN 1 ELSE 0 END) AS away
    FROM event e JOIN match m USING (match_id)
    GROUP BY e.match_id
)
SELECT m.match_id, m.home_goals, m.away_goals, COALESCE(g.home, 0), COALESCE(g.away, 0)
FROM match m LEFT JOIN goals g USING (match_id)
WHERE m.status = 'played'
  AND m.match_id IN (SELECT match_id FROM event)
  AND (m.home_goals <> COALESCE(g.home, 0) OR m.away_goals <> COALESCE(g.away, 0))
ORDER BY m.match_id
"""

_STARTERS_SQL = """
SELECT match_id, club_id, COUNT(*) FILTER (WHERE is_starter) AS starters
FROM lineup
GROUP BY match_id, club_id
HAVING starters <> 11
ORDER BY match_id, club_id
"""


def check_score_matches_events(con: duckdb.DuckDBPyConnection) -> list[Issue]:
    return [
        Issue("score_vs_events", mid, f"score {hg}-{ag} but events give {eh}-{ea}")
        for mid, hg, ag, eh, ea in con.execute(_SCORE_SQL).fetchall()
    ]


def check_eleven_starters(con: duckdb.DuckDBPyConnection) -> list[Issue]:
    return [
        Issue("eleven_starters", mid, f"club {club} has {n} starters")
        for mid, club, n in con.execute(_STARTERS_SQL).fetchall()
    ]


ALL_CHECKS = (check_score_matches_events, check_eleven_starters)


def run_all(con: duckdb.DuckDBPyConnection) -> list[Issue]:
    return [issue for check in ALL_CHECKS for issue in check(con)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_quality.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/quality/checks.py tests/test_quality.py
git commit -m "feat: data-quality checks"
```

---

### Task 10: CLI (`init-db`, `check`, `fetch`)

**Files:**
- Create: `src/ilfootball/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_settings` (1), `RawStore` (2), `HostRateLimiter` (3), `Fetcher`/`make_client` (4), `init_db` (6), `run_all` (9)
- Produces: `main(argv: list[str] | None = None) -> int`, also available as the `ilfootball` console script. `check` exits 1 when any issue is found. `fetch --source S --entity E --key K [--ext html] [--refresh] URL` downloads into the raw cache.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
from ilfootball.cli import main
from ilfootball.db.connect import init_db
from ilfootball.load.upsert import upsert
from ilfootball.models import Match, MatchEvent


def test_init_db_creates_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    assert main(["init-db"]) == 0
    assert (tmp_path / "ilfootball.duckdb").exists()
    assert "database ready" in capsys.readouterr().out


def test_check_clean_db_exits_zero(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    assert main(["check"]) == 0
    assert "0 issue(s)" in capsys.readouterr().out


def test_check_reports_issue_and_exits_one(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    con = init_db(tmp_path / "ilfootball.duckdb")
    upsert(con, [
        Match(match_id="ma-1", season_id="se-1", home_club_id="H", away_club_id="A",
              home_goals=1, away_goals=0, status="played"),
        MatchEvent(event_id="e1", match_id="ma-1", minute=5, club_id="A", type="goal"),
    ])
    con.close()
    assert main(["check"]) == 1
    assert "[score_vs_events] ma-1: score 1-0 but events give 0-1" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ilfootball.cli'`

- [ ] **Step 3: Write minimal implementation**

`src/ilfootball/cli.py`:

```python
"""Command line: `ilfootball init-db | check | fetch`."""
from __future__ import annotations

import argparse
import sys

from ilfootball.config import load_settings
from ilfootball.core.http import Fetcher, make_client
from ilfootball.core.ratelimit import HostRateLimiter
from ilfootball.core.raw_store import RawStore
from ilfootball.db.connect import init_db
from ilfootball.quality.checks import run_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ilfootball")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create the DuckDB database and schema")
    sub.add_parser("check", help="run data-quality checks; exit 1 if any issue")
    fetch = sub.add_parser("fetch", help="download one URL into the raw cache")
    fetch.add_argument("--source", required=True)
    fetch.add_argument("--entity", required=True)
    fetch.add_argument("--key", required=True)
    fetch.add_argument("--ext", default="html")
    fetch.add_argument("--refresh", action="store_true")
    fetch.add_argument("url")
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "init-db":
        init_db(settings.db_path).close()
        print(f"database ready: {settings.db_path}")
        return 0

    if args.command == "check":
        con = init_db(settings.db_path)
        issues = run_all(con)
        for issue in issues:
            print(f"[{issue.check}] {issue.match_id}: {issue.detail}")
        print(f"{len(issues)} issue(s)")
        return 1 if issues else 0

    if args.command == "fetch":
        store = RawStore(settings.raw_dir)
        with make_client(settings.user_agent) as client:
            fetcher = Fetcher(store, HostRateLimiter(settings.interval_for), client)
            body = fetcher.get(args.source, args.entity, args.key, args.url, args.ext, args.refresh)
        print(f"{len(body)} bytes -> {store.path_for(args.source, args.entity, args.key, args.ext)}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all 40 tests pass. Then run `uv run ilfootball init-db` and expect `database ready: data/ilfootball.duckdb`

- [ ] **Step 5: Commit**

```bash
git add src/ilfootball/cli.py tests/test_cli.py
git commit -m "feat: ilfootball CLI"
```

---

### Task 11: Source validation spike (run on a local machine)

The cloud sandbox can't reach the football sites, so **run this task on your own computer**. It produces the fixtures and facts that Plans 2–5 are written from.

**Files:**
- Create: `tests/fixtures/<source>/*` (copied from `data/raw/`)
- Create: `docs/source-findings.md`

**Interfaces:**
- Consumes: `ilfootball fetch` (Task 10)
- Produces: one real, saved page or JSON per source and entity type, plus `docs/source-findings.md` with one section per source. Each section answers the same questions (see Step 3).

- [ ] **Step 1: Find one real URL per source and entity in a browser**

For each row, open the site, go to the 2024/25 Ligat Ha'Al season, and copy the URL of the page described. For Sofascore and FotMob, open DevTools → Network → filter "api", and copy the JSON request URL the page makes.

| source | entity | page to find |
|---|---|---|
| `ifa` | `season_fixtures` | football.org.il → Ligat Ha'Al → games list for the season |
| `ifa` | `match` | one finished match's game page (lineups + events) |
| `ifa` | `standings` | league table for the season |
| `ifa` | `player` | one player page |
| `transfermarkt` | `squad` | transfermarkt.com → Maccabi Haifa → squad 2024/25 |
| `transfermarkt` | `player` | one player profile |
| `transfermarkt` | `transfers` | that player's transfer history |
| `sofascore` | `season_events` | `.../api/v1/unique-tournament/<id>/season/<id>/events/round/1` |
| `sofascore` | `match_stats` | `.../api/v1/event/<id>/statistics` |
| `sofascore` | `lineups` | `.../api/v1/event/<id>/lineups` |
| `fotmob` | `match` | `.../api/matchDetails?matchId=<id>` |
| `wikidata` | `clubs` | SPARQL query from Step 2 |

- [ ] **Step 2: Download each one into the raw cache**

```bash
uv run ilfootball fetch --source ifa --entity match --key 2024-25-r1-sample "<IFA match URL>"
uv run ilfootball fetch --source sofascore --entity lineups --key sample --ext json "<Sofascore lineups URL>"
# ...one command per row in the table above...

# Wikidata: Israeli association football clubs with Hebrew and English labels
uv run ilfootball fetch --source wikidata --entity clubs --key israel --ext json \
  "https://query.wikidata.org/sparql?format=json&query=SELECT%20%3Fclub%20%3Fhe%20%3Fen%20%3Ftm%20WHERE%20%7B%20%3Fclub%20wdt%3AP31%20wd%3AQ476028%3B%20wdt%3AP17%20wd%3AQ801.%20OPTIONAL%20%7B%3Fclub%20rdfs%3Alabel%20%3Fhe%20FILTER(lang(%3Fhe)%3D%22he%22)%7D%20OPTIONAL%20%7B%3Fclub%20rdfs%3Alabel%20%3Fen%20FILTER(lang(%3Fen)%3D%22en%22)%7D%20OPTIONAL%20%7B%3Fclub%20wdt%3AP7223%20%3Ftm%7D%20%7D"
```

Expected for each: `<N> bytes -> data/raw/<source>/<entity>/<key>.<ext>.gz`. If a command fails with `FetchError ... 403`, write that down in the findings. Don't retry more aggressively.

- [ ] **Step 3: Check whether the data is in the downloaded file (not added later by JavaScript)**

```bash
python -c "import gzip,sys;print(gzip.open(sys.argv[1]).read().decode()[:3000])" data/raw/ifa/match/2024-25-r1-sample.html.gz
```

Search the output for a player name you can see on the page. If it's missing, the page renders client-side: write "needs Playwright or a JSON endpoint" in the findings.

- [ ] **Step 4: Write `docs/source-findings.md`**

Use this exact structure for every source:

```markdown
## ifa
- URL patterns: season fixtures `...`, match `...`, standings `...`, player `...`
- Ids in URLs: match id = `...`, player id = `...`, club id = `...`
- Data present in HTML without JS: yes/no (per entity)
- Fields available: score, HT score, date/time, venue, referee, attendance, lineups, minutes, goals (+assist?), cards, subs
- Earliest season available: ....
- Languages: Hebrew page `...`, English page `...` (same ids?)
- Blocking / rate-limit behaviour seen: ...
- robots.txt notes: ...
```

- [ ] **Step 5: Copy the fixtures into the repo and commit**

```bash
mkdir -p tests/fixtures
for f in $(find data/raw -name '*.gz'); do
  rel=${f#data/raw/}; mkdir -p "tests/fixtures/$(dirname "$rel")"
  gunzip -c "$f" > "tests/fixtures/${rel%.gz}"
done
git add tests/fixtures docs/source-findings.md
git commit -m "docs: source validation spike findings and parser fixtures"
```

- [ ] **Step 6: Hand off**

Bring `docs/source-findings.md` back to the planning session. Plan 2 (IFA core) is written next, against these fixtures.
