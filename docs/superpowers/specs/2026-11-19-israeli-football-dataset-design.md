# Israeli Football Dataset — Design

**Status:** draft for review · **Date:** 2026-11-19
**Builds on:** [`docs/DATA_PLAN.md`](../../DATA_PLAN.md) (sources, storage choice, data model)

This document turns the data plan into a buildable design. It covers the
components, how data moves between them, the interfaces between them, how
errors and data quality are handled, how it's tested, and the order of
sub-projects. Each sub-project gets its own implementation plan in
`docs/superpowers/plans/`.

---

## 1. Goals and non-goals

**Goals**
- A reproducible pipeline that builds an Israeli football database from free
  sources only, and can be rebuilt from cached raw files without hitting any
  website again.
- One canonical record per real-world club, player, match and competition,
  linked to every source's own id.
- Automatic data-quality checks that block bad data before it reaches the
  website.
- Incremental daily updates that cost $0 to run (GitHub Actions).

**Non-goals (for now)**
- The website itself. The pipeline's output is a DuckDB file plus JSON exports.
- Real-time live scores.
- Copyrighted media such as photos, articles and video.

---

## 2. Architecture

```
                 ┌────────────────────────────────────────────────────────┐
                 │                    ilfootball (Python)                 │
                 │                                                        │
  websites ──▶  │  sources/<src>/fetch.py ──▶ core.http.Fetcher ──▶ RawStore │──▶ data/raw/**.gz
                 │        (which URLs)          (rate limit, retry,         │    (immutable cache)
                 │                               cache-first)               │
                 │                                                        │
                 │  sources/<src>/parse.py  ◀── RawStore.load()            │
                 │        (bytes ──▶ source-specific records)              │
                 │                │                                       │
                 │                ▼                                       │
                 │  sources/<src>/transform.py                            │
                 │        (records ──▶ models.Row, ids via resolve.IdMap) │
                 │                │                                       │
                 │                ▼                                       │
                 │  load.upsert(con, rows) ──▶ DuckDB core tables          │──▶ data/ilfootball.duckdb
                 │                │                                       │
                 │                ▼                                       │
                 │  quality.run_all(con) ──▶ Issues (CI fails if any)      │
                 │                │                                       │
                 │                ▼                                       │
                 │  export/ ──▶ JSON / Parquet / Postgres for the website   │──▶ site
                 └────────────────────────────────────────────────────────┘
```

### Components

| Module | Responsibility | Knows about sources? |
|---|---|---|
| `config` | Settings from env: data dir, User-Agent, per-host intervals | no |
| `core.raw_store` | Save and load gzip-compressed raw responses at `raw/<source>/<entity>/<key>.<ext>.gz` | no |
| `core.ratelimit` | Minimum gap (plus jitter) between requests to the same host | no |
| `core.http` | `Fetcher.get()`: cache-first, rate-limited, retries 429/5xx, saves only on 200 | no |
| `db` | `schema.sql` and `init_db()` | no |
| `models` | Pydantic row types. Field names are the same as column names | no |
| `load.upsert` | Insert or replace rows by primary key | no |
| `resolve.normalize` | Hebrew/Latin name normalisation (`normalize_name`, `name_key`) | no |
| `resolve.id_map` | Source id → canonical id; `mint`, `register`, `resolve_player` | no |
| `quality.checks` | SQL checks that return `Issue` lists | no |
| `sources.<src>` | `fetch.py` (URL discovery), `parse.py` (bytes → records), `transform.py` (records → rows) | **yes, one package per source** |
| `cli` | `init-db`, `check`, `fetch`, later `sync <source>` and `export` | no |

**Main rule:** everything above `sources/` is source-agnostic. Adding a source
means adding a new `sources/<name>/` package. Nothing else changes.

### Source adapter contract (used from Plan 2 onward)

Every source package exposes three steps that can each be tested separately:

```python
# sources/<src>/fetch.py
def discover(fetcher: Fetcher, season: str) -> list[RawRef]: ...    # downloads into RawStore
# sources/<src>/parse.py
def parse_<entity>(raw: bytes) -> list[<Src>Record]: ...            # pure, no I/O
# sources/<src>/transform.py
def to_rows(records, ids: IdMap) -> list[Row]: ...                  # assigns canonical ids
```

`parse_*` functions are pure, so they're tested against **saved fixture files**
in `tests/fixtures/<src>/` and never against the live site.

---

## 3. Data flow and ids

1. **Fetch:** `Fetcher.get(source, entity, key, url)` returns bytes. A cached
   response is never fetched again unless `refresh=True` is passed. Pages that
   change, such as season fixture lists and standings, are refreshed. Finished
   match pages are not.
2. **Parse:** bytes become source records with the source's own ids and the raw
   names as they appear.
3. **Resolve ids:** `IdMap.lookup()` checks for an existing mapping. If there
   isn't one, `resolve_player()` tries an exact name plus date-of-birth match,
   then a fuzzy name plus date-of-birth match (score ≥ 90). If both fail it
   *mints* a new id `pl-<source>-<source_id>`. Clubs and competitions come from
   a hand-curated `reference/*.csv` file.
4. **Load:** `upsert()` is idempotent, so running the same input twice gives the
   same database.
5. **Check:** `quality.run_all()`. A non-zero issue count fails the CLI and CI.

**Canonical id format:** `<prefix>-<first_source>-<source_id>`, e.g.
`pl-ifa-4411`. It's readable, deterministic and stable across rebuilds. When
another source sees the same player later, it maps to the existing id.

**Source priority (who owns which field):** IFA owns matches, lineups and
events. Transfermarkt owns transfers and market values. Sofascore/FotMob own
advanced stats. Wikidata owns bios and Hebrew/English labels. Later sources fill
fields that are empty but never overwrite an owned field.

---

## 4. Error handling

| Situation | Behaviour |
|---|---|
| 429 / 5xx / network error | Retry with exponential backoff (`5s · 2^n`, max 4 retries), then `FetchError` |
| 404 / 403 / other 4xx | `FetchError` right away. Nothing is cached |
| Parser meets an unexpected layout | Raise with source, key and the failing selector. The raw file stays cached, so after a parser fix only parsing is re-run |
| Name can't be matched confidently | Mint a new id with `method='minted'`. Plan 3 adds a review CSV for name-only near-matches |
| Quality issue | Report it and exit 1. CI blocks the export |
| Site blocks us | Stop that source. Never rotate proxies or evade blocks. The other sources keep working |

---

## 5. Testing strategy

- **Unit tests** for every core module, using fakes for the clock, sleep and
  HTTP (`httpx.MockTransport`). There is no network access in tests.
- **Parser tests** against real saved pages in `tests/fixtures/<src>/`, captured
  once during the Plan 1 spike (Task 11).
- **Quality checks** tested with small synthetic datasets.
- **End-to-end smoke test** (Plan 2): fixtures → parse → transform → upsert →
  checks give 0 issues.
- Run with `uv run pytest`. CI runs the same command on every push.

---

## 6. Sub-projects and task breakdown

Each sub-project produces working, tested software on its own and gets its own
detailed plan. **Plan 1 is fully written.** Plans 2–7 are written in detail when
they start, because each depends on what the Task 11 spike finds out about the
real HTML and JSON.

### Plan 1 — Pipeline foundation *(detailed plan ready)*
`docs/superpowers/plans/2026-11-19-plan-1-pipeline-foundation.md`
1. Project scaffold and settings
2. Raw response store
3. Per-host rate limiter
4. Polite HTTP fetcher
5. Hebrew/Latin name normalisation
6. Canonical DuckDB schema
7. Row models and upsert
8. ID map and player resolution
9. Data-quality checks
10. CLI (`init-db`, `check`, `fetch`)
11. Source validation spike: capture fixtures and write the findings

### Plan 2 — IFA core (Ligat Ha'Al, last 5 seasons)
1. Reference data: `reference/competitions.csv` and `reference/clubs.csv` (HE/EN names, IFA ids)
2. IFA fixture-list discovery per season → match keys
3. IFA match page parser: score, date, venue, referee, attendance
4. IFA lineup parser: starters, subs, shirt numbers, minutes
5. IFA events parser: goals, own goals, penalties, cards, subs
6. IFA standings parser, including the championship/relegation split
7. Transform to rows with IdMap, plus the end-to-end fixture test
8. `ilfootball sync ifa --season 2025/26` command, incremental by default
9. Quality checks added: minutes ≤ 120 and standings points equal to results

### Plan 3 — Identity and enrichment
1. Wikidata SPARQL client: Israeli clubs and players with HE/EN labels and TM/Sofascore/FBref ids
2. Seed `id_map` from Wikidata cross-ids
3. Review queue: name-only near-matches written to `reference/review/players.csv`, with manual overrides read back
4. Player bio enrichment: DOB, nationality, position, height

### Plan 4 — Transfermarkt
1. Squad pages per club and season → `squad_membership`
2. Player profile → bio fields and market value history (`market_value` table)
3. Transfer history (`transfer` table)
4. Coaches and tenures (`coach`, `coach_tenure`)
5. Injuries (`injury`)

### Plan 5 — Advanced stats (Sofascore, with FotMob as backup)
1. Tournament and season id discovery for Ligat Ha'Al
2. Event list → map each Sofascore match to its canonical match (date + clubs)
3. Team match stats (`team_match_stats`): possession, shots, xG
4. Player match stats (`player_match_stats`): rating, xG, xA, passes, and so on
5. FotMob adapter as a fallback and xG cross-check

### Plan 6 — Breadth and history
1. Liga Leumit, State Cup, Toto Cup, women's league (reusing the IFA adapter)
2. European matches of Israeli clubs (UEFA.com)
3. Historical backfill from Worldfootball.net and Wikipedia/RSSSF
4. Our own Elo ratings computed from the match table

### Plan 7 — Automation and serving
1. GitHub Actions nightly `sync` → `check` → `export`
2. Raw cache backup to a free bucket (Cloudflare R2 free tier or Google Drive)
3. JSON/Parquet exports for the website, and optional Supabase Postgres sync
4. Freshness report (latest match per competition, issue counts)

---

## 7. Decisions still open (from the data plan)

These don't block Plan 1. They do decide the scope of Plans 2 to 6:
1. Which leagues to cover first (Ligat Ha'Al only, or all tiers).
2. How far back the history goes.
3. Whether the site is Hebrew first, English first, or both.
4. Whether unofficial sources (Sofascore, FotMob, Transfermarkt) are acceptable.
5. Static JSON or a Supabase database for serving.
