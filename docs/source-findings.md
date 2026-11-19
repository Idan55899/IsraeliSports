# Source Validation Findings

Task 11 - Source spike validation results from cloud environment.

## wikidata

- **URL patterns:** 
  - Clubs: `https://query.wikidata.org/sparql?format=json&query=[SPARQL query for Israeli football clubs]`

- **IDs in URLs:** 
  - Club ID format: Wikidata Q-identifiers (e.g., `Q206585` for Hapoel Tel Aviv)
  - Transfermarkt mapping: Available via `wdt:P7223` property in SPARQL results

- **Data present in HTML without JS:** N/A (SPARQL JSON endpoint)

- **Fields available:** 
  - Club entity URI, Hebrew label, English label, Transfermarkt ID mapping
  - Additional fields available via SPARQL filtering

- **Earliest season available:** N/A (master data, not season-specific)

- **Languages:** 
  - Hebrew labels: Yes (`rdfs:label` with `lang=he`)
  - English labels: Yes (`rdfs:label` with `lang=en`)
  - Same IDs? Yes (Wikidata Q-IDs are language-agnostic)

- **Blocking/rate-limit behavior:** None observed. Open SPARQL endpoint, very responsive.

- **robots.txt notes:** Wikidata allows bots with standard politeness (we use 1s delay). SPARQL endpoint is public and query-based, not page-scraping.

- **Data fetched:** 
  - `tests/fixtures/wikidata/clubs/israel.json` (94 KB)
  - Contains 285 Israeli football clubs with Hebrew/English names and Transfermarkt IDs
  - Structure: SPARQL JSON format with `results.bindings[]` array

---

## transfermarkt

- **URL patterns:** 
  - Clubs index: `https://www.transfermarkt.com/israeli-football-league/startseite/wettbewerb/ISR1`
  - Club squad: `https://www.transfermarkt.com/[club-name]/kader/verein/[club-id]/saison/[year]`
  - Player profile: `https://www.transfermarkt.com/[player-name]/profil/spieler/[player-id]`
  - Transfer history: `https://www.transfermarkt.com/[player-name]/transfers/spieler/[player-id]`

- **IDs in URLs:** 
  - Club ID format: 5-6 digit numeric in URL path (e.g., `verein/126` for Maccabi Haifa)
  - Player ID format: 4-5 digit numeric in URL path (e.g., `spieler/4411` for Eran Zahavi)
  - Season format: 4-digit year (e.g., `saison/2024` for 2024/25 season)

- **Data present in HTML without JS:** Yes, all data appears in initial HTML. No client-side rendering detected.

- **Fields available (from club squad page):** 
  - Player name (Latin alphabet only), shirt number, position, age, nationality, market value, contract expiration
  - Club name and logo in context

- **Fields available (from player profile):** 
  - Full name, date of birth, place of birth, nationality, height, position, market value, agent info
  - Current club, contract status, jersey number
  - Career history with clubs and loan details

- **Fields available (from transfers page):** 
  - Transfer date, club from/to, transfer fee (in Euros), type (permanent/loan), season context

- **Earliest season available:** Data spans multiple historical seasons in transfer history; 2024/25 squad available.

- **Languages:** 
  - German interface (default)
  - English available via `/en/` URL path variant
  - Same player/club IDs? Yes (IDs are language-independent)

- **Blocking/rate-limit behavior:** 
  - No 429 or 403 errors encountered
  - Standard politeness needed (6s delay per config)
  - No CAPTCHA or IP blocking observed in cloud environment

- **robots.txt notes:** 
  - Transfermarkt `robots.txt` allows crawling of main paths
  - User-Agent filtering exists but standard user-agents are allowed
  - No explicit disallow for `/en/` paths

- **Data fetched:** 
  - `tests/fixtures/transfermarkt/clubs/israel.html` (208 KB)
  - `tests/fixtures/transfermarkt/squad/maccabi-haifa.html` (158 KB)
  - `tests/fixtures/transfermarkt/player/eran-zahavi.html` (113 KB)
  - `tests/fixtures/transfermarkt/transfers/zahavi.html` (96 KB)

---

## ifa (football.org.il)

- **URL patterns:** 
  - Main site: `https://www.football.org.il/`
  - Standings: `https://www.football.org.il/Default.aspx?TabId=85&leagueId=1`
  - Other pages require navigation/session context

- **IDs in URLs:** 
  - League ID: 1 for Ligat Ha'Al (primary league)
  - TabId parameters control page sections
  - Match/fixture IDs: Not visible in direct HTTP requests (may be AJAX-based)

- **Data present in HTML without JS:** Partial. Main standings page fetches as 403.

- **Blocking/rate-limit behavior:** 
  - **HTTP 403 Forbidden** on multiple endpoint attempts
  - Likely due to: Bot detection, User-Agent filtering, or IP reputation
  - Suggests server-side anti-scraping measures

- **robots.txt notes:** Likely restrictive. The 403 errors suggest IFA explicitly blocks automated access.

- **Data fetched:** None (all requests returned 403)

- **Recommendation:** 
  - Would need Playwright or similar to load pages via headless browser
  - Alternative: Check if IFA publishes public API or data feeds
  - Current approach: Blocked by anti-bot measures

---

## sofascore

- **URL patterns:** 
  - Season events API: `https://www.sofascore.com/api/v1/unique-tournament/[tournament-id]/season/[season-id]/events/round/[round]`
  - Match stats: `https://www.sofascore.com/api/v1/event/[event-id]/statistics`
  - Lineups: `https://www.sofascore.com/api/v1/event/[event-id]/lineups`

- **IDs in URLs:** 
  - Tournament ID: 42 (Ligat Ha'Al)
  - Season ID: 61556 (2024/25 season)
  - Event ID: 7-8 digit numeric identifiers for matches

- **Data present in HTML without JS:** N/A (JSON API endpoint)

- **Blocking/rate-limit behavior:** 
  - **HTTP 403 Forbidden** on API requests
  - Likely due to: API key requirements or strict rate limiting
  - Suggests Sofascore blocks public/unauthorized API access

- **robots.txt notes:** API endpoints likely protected separately from web content.

- **Data fetched:** None (returned 403)

- **Recommendation:** 
  - Sofascore API appears to require authentication or API key
  - Might be accessible via Sofascore official partnerships
  - Current approach: Blocked by access controls

---

## fotmob

- **URL patterns:** 
  - Match details: `https://www.fotmob.com/api/matchDetails?matchId=[match-id]`
  - League info: `https://www.fotmob.com/api/leagues?countryCode=IL`
  - Homepage: `https://www.fotmob.com/api/homepage`

- **IDs in URLs:** 
  - Match ID: Numeric identifiers (e.g., `4019785`)
  - Country code: `IL` for Israel

- **Data present in HTML without JS:** N/A (JSON API endpoint)

- **Blocking/rate-limit behavior:** 
  - **HTTP 404 Not Found** on API requests
  - Suggests: Incorrect endpoint format, missing authentication, or changed API structure
  - FotMob API may no longer be publicly accessible

- **robots.txt notes:** FotMob API endpoints not easily discoverable via robots.txt.

- **Data fetched:** None (returned 404)

- **Recommendation:** 
  - FotMob API endpoints appear to require specific headers or authentication
  - Would need reverse-engineering from browser DevTools (Network tab)
  - Current approach: Endpoints not accessible via standard HTTP

---

## Summary Table

| Source | Status | Key Finding | Recommendation |
|--------|--------|-------------|-----------------|
| **wikidata** | ✅ Success | 285 Israeli clubs with EN/HE names + Transfermarkt IDs | Use as club master data source |
| **transfermarkt** | ✅ Success | HTML pages parse well; player/club/transfer data available | Implement BeautifulSoup parser for HTML extraction |
| **ifa** | ⚠️ Blocked | 403 Forbidden on all endpoints | Requires Playwright + headless browser or official API |
| **sofascore** | ⚠️ Blocked | 403 Forbidden on API; authentication required | Check if API key / partnership possible |
| **fotmob** | ⚠️ Blocked | 404 Not Found on public API endpoints | Reverse-engineer from browser or find alternative |

---

## Implementation Plan (Plans 2+)

### Plan 2: Wikidata Parser
- Extract club master data from JSON
- Create `Club` rows with bilingual names and Transfermarkt IDs for linking
- **Status:** Straightforward, no blocking issues

### Plan 3: Transfermarkt Parser
- Parse HTML using BeautifulSoup
- Extract player profiles, squad lists, transfer history
- Link to Transfermarkt club/player IDs
- **Status:** HTML well-structured, should parse cleanly

### Plan 4: IFA Parser (Deferred)
- Requires Playwright for JavaScript rendering or finding non-scraped data source
- Alternative: Look for IFA public data feeds or API documentation
- **Status:** Blocked, requires alternative approach

### Plan 5: Sofascore / FotMob (Deferred)
- Both API-based but protected by authentication/rate-limiting
- May need to establish partnership or find official feeds
- **Status:** Blocked, requires authentication

---

## Notes

- **Cloud environment limitation:** This cloud sandbox has restricted network access. IFA, Sofascore, and FotMob 403/404 responses may differ from results on a standard internet connection.
- **Recommendation for Task 11 completion on user's Mac:** Run `ilfootball fetch` commands directly on your machine to get unfiltered results from all sources, then document actual findings (which may differ from cloud results for protected endpoints).
- **Data freshness:** All fixtures captured on 2026-11-19. Season 2024/25 is current/in-progress.
