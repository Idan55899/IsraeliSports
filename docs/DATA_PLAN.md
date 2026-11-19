# Israeli Football Dataset — Data Acquisition & Storage Plan

Goal: build a free, self-maintained dataset of Israeli football (teams, players,
matches, events, stats, transfers, history) to feed an insights website.

Constraint: **no paid services or paid APIs.** Free tiers and public pages only.

---

## 1. What data we want

| Domain | Examples | Priority |
|---|---|---|
| Competitions & seasons | Ligat Ha'Al, Liga Leumit, Liga Alef, State Cup, Toto Cup, Super Cup; seasons back to the 1990s or earlier | P0 |
| Clubs | Name (HE/EN), city, stadium, founding year, colours, logo URL | P0 |
| Matches | Date, round, venue, referee, score, attendance | P0 |
| Lineups & minutes | Starting XI, subs, minutes played, captain | P0 |
| Match events | Goals (minute, assist, penalty/own goal), cards, substitutions | P0 |
| Standings | Per round table snapshots, including the championship/relegation split | P0 |
| Players | Name (HE/EN), DOB, nationality, position, foot, height | P0 |
| Advanced stats | xG, shots, passes, ratings, shot maps | P1 |
| Transfers & market values | Fee, from/to club, contract end, value history | P1 |
| Injuries/suspensions | Type, dates, games missed | P2 |
| Coaches | Tenures per club, record per tenure | P1 |
| European games | Israeli clubs in UCL/UEL/UECL qualifiers, national team | P1 |
| Club strength | Elo ratings over time | P2 |

---

## 2. Free data sources

Ranked by how much each one is worth to us. **Prefer official and open sources;
use the unofficial ones carefully** (see section 7).

| # | Source | What it gives | How to get it | Notes / risk |
|---|---|---|---|---|
| 1 | **Israel Football Association** – `football.org.il` | Official data for **every** league tier: fixtures, results, lineups, goals, cards, subs, referees, standings, player pages | HTML scraping (Hebrew + partial English pages) | Most authoritative source, and the only one that covers the lower leagues well. Pages can be slow or awkward to parse; some are ASP.NET forms. |
| 2 | **Ligat Ha'Al official site** (`ligathaal.co.il`) and club sites | Top-flight fixtures, stats, news | HTML scraping | Useful for cross-checking. Coverage changes from season to season. |
| 3 | **Transfermarkt** | Market values, transfers, contracts, injuries, squad lists, coaches, long history | HTML scraping (no official API). Community scrapers such as `transfermarkt-api` and `transfermarkt-datasets` on GitHub show the patterns | Best source for transfers and values. ToS discourages scraping, so keep it slow and low-volume and cache everything. |
| 4 | **Sofascore** (unofficial JSON API) | Ligat Ha'Al match stats, player ratings, xG, shot maps, heatmaps, lineups | JSON endpoints behind their web app, e.g. `/api/v1/unique-tournament/{id}/season/{id}/events`, `/api/v1/event/{id}/lineups` | Richest free advanced stats for Israel. Unofficial and ToS-restricted. Endpoints change and they block aggressive clients. |
| 5 | **FotMob** (unofficial JSON API) | xG, shot maps, ratings, lineups (league id 127 = Ligat Ha'Al) | JSON endpoints used by the website | Same caveats as Sofascore. Good backup or cross-check for xG. |
| 6 | **FBref** | Season tables, player stats | HTML tables (easy with `pandas.read_html`) | Advanced (Opta) stats are limited or no longer available. Treat it as basic stats only. Strict rate limit (about 10 requests per minute). |
| 7 | **Worldfootball.net** | Long historical results, top scorers, lineups for older seasons | HTML scraping | Good for backfilling history from before the IFA site's coverage. |
| 8 | **Wikipedia + Wikidata** | Club and stadium metadata, historical champions, player bios, Hebrew/English name pairs, cross-site IDs | Wikidata SPARQL (`query.wikidata.org`), MediaWiki API | **Fully open (CC0/CC-BY-SA)**. Wikidata stores Transfermarkt/Soccerway/FBref IDs, which helps a lot with entity matching. |
| 9 | **API-Football (free tier)** | Fixtures, events, lineups, player stats; covers the Israeli leagues | REST API, free plan of about 100 requests per day | Free and legal, but the daily quota is small. Use it for gap-filling and ID mapping, not bulk history. |
| 10 | **ClubElo** (`api.clubelo.com`) | Daily Elo ratings as CSV | Simple CSV API | Check how well it covers Israeli clubs. Free and open. |
| 11 | **UEFA.com** | Israeli clubs' European matches, coefficients | HTML/JSON | Official. Use for European and national-team data. |
| 12 | **Kaggle / GitHub datasets** | One-off historical dumps (Transfermarkt datasets, international results) | Download CSV | Quick bootstrap. Check the licence of each dataset. |

**Python helpers worth using:** `soccerdata` (wraps FBref, Sofascore, FotMob,
ClubElo and others with caching built in), `httpx`, `selectolax` or
`BeautifulSoup`, `pandas`, and `playwright` for pages that need JavaScript.

> Note: I couldn't reach these hosts from the cloud sandbox where this plan was
> written because its network allowlist blocks them. Section 8 starts with a
> validation spike that runs locally.

---

## 3. Source-to-data mapping (who is the "source of truth")

| Data | Primary | Fallback / enrichment |
|---|---|---|
| Fixtures, results, lineups, events (all tiers) | IFA | Sofascore, Worldfootball.net, API-Football |
| Advanced stats (xG, ratings, shots) | Sofascore | FotMob |
| Transfers, market values, contracts, injuries | Transfermarkt | Wikipedia |
| Player and club bios, HE/EN names | Wikidata | IFA, Transfermarkt |
| History before about 2000 | Worldfootball.net, Wikipedia | RSSSF pages |
| European competitions | UEFA.com | Sofascore |
| Elo | ClubElo | Compute our own Elo from our match table |

Each field is owned by one source. Other sources are only used to fill gaps
or to raise conflicts for review.

---

## 4. Storage architecture

A layered "medallion" design: cheap, reproducible, and starts on a laptop.

```
          ┌──────────── scrapers / fetchers (Python) ────────────┐
          │  ifa  transfermarkt  sofascore  fotmob  wikidata ... │
          └──────────────────────────┬────────────────────────────┘
                                     ▼
 RAW (bronze)   data/raw/<source>/<entity>/<date>/<id>.html|json   ← immutable, gzip
                                     ▼  parsers
 STAGING (silver) data/staging/<source>/<entity>.parquet            ← one table per source, typed
                                     ▼  entity resolution + merge
 CORE (gold)    DuckDB file  data/israelfootball.duckdb             ← canonical schema (section 5)
                                     ▼  export / sync
 SERVING        Postgres (Supabase free tier or local) / static JSON for the website
```

**Why this design**
- **Raw cache first.** Every HTTP response is saved before it is parsed. A parser
  bug then means re-parsing the files, not re-scraping, which keeps traffic to
  the sources low.
- **Parquet + DuckDB** for the analytics core. It's free, a single file, very
  fast for aggregations ("most goals after the 80th minute"), and needs no
  server.
- **Postgres** (Supabase free tier, or Neon or local Docker) only when the
  website needs a live DB. Before that, the site can read pre-computed JSON
  exported from DuckDB, which is faster and free to host on Vercel or GitHub
  Pages.
- Raw data stays out of git (`.gitignore`) and gets backed up to a free bucket
  (Cloudflare R2 free tier or Google Drive). Small curated tables, such as the
  ID crosswalk and the club list, are committed to git.

---

## 5. Canonical data model (core layer)

```
competition(competition_id, name_en, name_he, tier, type[league|cup|europe])
season(season_id, competition_id, label '2025/26', start_date, end_date)
club(club_id, name_en, name_he, short_name, city, founded, stadium_id, wikidata_qid)
stadium(stadium_id, name_en, name_he, city, capacity, lat, lon)
player(player_id, full_name_en, full_name_he, birth_date, nationality, position, foot, height_cm, wikidata_qid)
coach(coach_id, name_en, name_he, birth_date, nationality)
referee(referee_id, name_en, name_he)

match(match_id, season_id, round, stage[regular|championship|relegation|cup_rd],
      date_utc, home_club_id, away_club_id, home_goals, away_goals,
      ht_home, ht_away, stadium_id, referee_id, attendance, status)
lineup(match_id, club_id, player_id, shirt_no, is_starter, position, minutes, is_captain)
event(event_id, match_id, minute, added_time, club_id, player_id, type[goal|own_goal|pen_goal|pen_miss|yellow|second_yellow|red|sub_in|sub_out],
      related_player_id /* assist or sub partner */)
player_match_stats(match_id, player_id, rating, shots, shots_on, xg, xa, passes, key_passes, tackles, ... , source)
team_match_stats(match_id, club_id, possession, shots, xg, corners, fouls, ..., source)
standing(season_id, round, club_id, position, played, w, d, l, gf, ga, pts)

squad_membership(season_id, club_id, player_id, shirt_no, from_date, to_date)
transfer(transfer_id, player_id, from_club_id, to_club_id, date, fee_eur, type[loan|permanent|free|end_of_loan], source)
market_value(player_id, date, value_eur)
injury(player_id, from_date, to_date, type, games_missed)
coach_tenure(coach_id, club_id, from_date, to_date)

-- the important glue table:
id_map(entity_type, canonical_id, source, source_id, source_name, confidence, verified_by)
```

---

## 6. The hard part: entity resolution (HE/EN names)

The same player can show up as "Eran Zahavi", "ערן זהבי", "E. Zehavi" and
"Zahavi Eran", depending on the source. Club names vary too: "Maccabi Tel Aviv",
"Maccabi Tel-Aviv FC", "מכבי ת״א".

Approach:
1. **Seed with Wikidata.** Many entries already link Transfermarkt, Soccerway
   and FBref IDs, plus Hebrew and English labels.
2. **Deterministic match** on (source ID crosswalk) → (DOB + club + season) →
   (shirt number + match + club).
3. **Fuzzy match** with `rapidfuzz` on normalised, transliterated names, and
   Hebrew normalisation (strip niqqud, ״/׳, final letters).
4. Store the result in `id_map` with a confidence score. Low-confidence matches
   go to a small review CSV that a person checks by hand.
5. Clubs and competitions are few (hundreds), so their mapping is curated by
   hand once and committed to git.

---

## 7. Scraping rules (legal, polite, sustainable)

- Read `robots.txt` and the ToS of each site, and prefer official and open
  sources (IFA, Wikidata, UEFA, the API-Football free tier).
- **Rate limit** every source. Defaults: 1 request every 3–6 s with jitter, one
  connection per host, exponential backoff on 429/5xx.
- Identify politely with a stable User-Agent. Don't rotate proxies or evade
  blocks.
- **Cache forever and fetch incrementally.** History is scraped once. After that,
  only new or changed matches are fetched.
- Store facts (scores, minutes, stats), not copyrighted content (photos, articles).
  Credit sources on the website. Facts are generally not copyrightable, but
  republishing a site's whole database can still conflict with its ToS. Keep the
  unofficial sources (Sofascore, FotMob, Transfermarkt) as enrichment, and be
  ready to drop them.
- Be careful with logos and player photos. Link to them or use open-licence
  images (Wikimedia Commons).

---

## 8. Implementation phases

**Phase 0 — Validation spike (1–2 days)**
- From a local machine, fetch one Ligat Ha'Al season from each source: IFA,
  Transfermarkt, Sofascore, FotMob, Wikidata and API-Football.
- Record which fields each source actually has, how far back its history goes,
  whether pages need JavaScript, and when it starts blocking. Update section 3
  with the findings.

**Phase 1 — Skeleton + IFA core (1 week)**
- Repo layout (below), config, HTTP client with caching and rate limiting,
  DuckDB schema.
- IFA scraper → competitions, seasons, clubs, matches, lineups, events,
  standings for the last 5 Ligat Ha'Al seasons.
- Data quality checks: goals in events match the final score, 11 starters per
  side, minutes ≤ 120.

**Phase 2 — Enrichment (1–2 weeks)**
- Wikidata seeding of clubs and players plus the ID crosswalk.
- Transfermarkt: squads, values, transfers.
- Sofascore/FotMob: advanced match and player stats.
- Entity-resolution pipeline + review CSV.

**Phase 3 — Breadth & history**
- Liga Leumit, State Cup, Toto Cup, the women's league, European matches.
- Historical backfill (Worldfootball.net, Wikipedia, RSSSF).

**Phase 4 — Automation & serving**
- Scheduled incremental updates with **GitHub Actions cron** (free), e.g. a
  nightly run, plus extra runs after match days.
- Export gold tables → Postgres (Supabase free) and/or static JSON for the
  website.
- Data freshness and quality report on every run.

**Phase 5 — Derived insights (feeds the website)**
- Our own Elo and form tables, home/away splits, goal timing, player per-90
  stats, age curves, squad value against league position, referee card rates,
  and comeback and late-goal stats.

---

## 9. Proposed repo layout

```
israelisports/
├── docs/DATA_PLAN.md
├── pipeline/
│   ├── core/            # http client (cache + rate limit), storage, logging
│   ├── sources/
│   │   ├── ifa/         # fetch.py, parse.py
│   │   ├── transfermarkt/
│   │   ├── sofascore/
│   │   ├── fotmob/
│   │   └── wikidata/
│   ├── resolve/         # entity resolution, id_map
│   ├── load/            # staging → DuckDB core, exports
│   └── quality/         # validation checks
├── reference/           # curated, committed CSVs: clubs.csv, competitions.csv, id_map_overrides.csv
├── data/                # gitignored: raw/, staging/, *.duckdb
├── tests/               # parser tests against saved HTML/JSON fixtures
└── .github/workflows/   # scheduled updates
```

**Tech stack:** Python 3.12, `uv`, `httpx`, `selectolax`/`bs4`, `playwright`
(only if needed), `pandas`/`polars`, `duckdb`, `rapidfuzz`, `pydantic`,
`pytest`. Total cost: **$0**.

---

## 10. Open questions for you

1. **Scope:** top flight only at first, or all tiers and the women's league
   from the start?
2. **History depth:** last 5–10 seasons, or as far back as possible (1949+)?
3. **Language:** should the site be Hebrew first, English first, or both? This
   decides how much effort goes into name pairs.
4. **Comfort with unofficial sources:** OK to use Sofascore, FotMob and
   Transfermarkt, slowly and cached, for xG, ratings and values? Or official and
   open sources only?
5. **Serving DB:** fine with Supabase's free tier, or keep everything static
   (DuckDB → JSON) at first?
