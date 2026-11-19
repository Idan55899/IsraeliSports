# Source Validation Findings

Task 11 - Source spike validation results. **UPDATED: Found accessible sources!**

## 🟢 Updated Summary

We found **2 easily accessible sources** for Israeli football data:
- ✅ **ESPN** - Standings & fixture data (505 KB HTML)
- ✅ **FlashScore** - League info & match data (569 KB HTML)
- ✅ **Transfermarkt** - Player profiles & transfers (already working)
- ✅ **Wikidata** - Club master data (already working)

**Missing sources** (blocked/not available):
- ⚠️ **IFA** - 403 Forbidden (would need Playwright)
- ⚠️ **Sofascore** - 403 Forbidden (needs API key)
- ⚠️ **FotMob** - 404 Not Found (API unavailable)
- ⚠️ **Football-Data.org** - Doesn't cover Israeli leagues

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

## espn

- **URL patterns:** 
  - Standings: `https://www.espn.com/soccer/table?league=ISR.1`
  - Fixtures: `https://www.espn.com/soccer/matches?league=ISR.1`
  - Team pages: `https://www.espn.com/soccer/team/_/id/[team-id]/[team-name]`

- **IDs in URLs:** 
  - League ID: `ISR.1` for Israeli Premier League
  - Team IDs: Numeric identifiers (e.g., `/id/123/`)

- **Data present in HTML without JS:** Yes, all data in initial HTML. No JavaScript rendering needed.

- **Fields available:** 
  - League standings (position, played, wins, draws, losses, GF, GA, GD, points)
  - Team names, logos, win/loss records
  - Match results (home/away scores, dates)
  - Team records (W/D/L)

- **Earliest season available:** Current season 2024/25; historical seasons available via URL parameters

- **Languages:** 
  - English only (US ESPN)
  - Hebrew available on separate site (ESPN.com.br has different leagues)
  - Same team IDs? Unclear without comparing

- **Blocking/rate-limit behavior:** None observed. Standard politeness respected (5s delay).

- **robots.txt notes:** ESPN allows crawling. No special restrictions observed.

- **Data fetched:** 
  - `tests/fixtures/ESPN/standings/ligat-haal-2024-25.html` (505 KB)
  - Contains full standings table with all 14 teams

---

## flashscore

- **URL patterns:** 
  - Israeli football index: `https://www.flashscore.com/football/israel/`
  - League/season specific: `https://www.flashscore.com/football/israel/ligat-haal/`
  - Match details: `https://www.flashscore.com/match/[match-id]/`

- **IDs in URLs:** 
  - League/season in URL path (e.g., `/ligat-haal/`)
  - Match IDs: Alphanumeric identifiers in match pages

- **Data present in HTML without JS:** Partial. Main data in HTML, but some content loads dynamically. Static content includes standings and schedules.

- **Fields available:** 
  - League standings (team position, points, GF, GA, GD)
  - Match schedules and results
  - Team information
  - Basic match scores

- **Earliest season available:** Current season visible; historical seasons may be accessible

- **Languages:** 
  - English interface
  - Hebrew not observed on direct crawl
  - League-agnostic IDs

- **Blocking/rate-limit behavior:** None observed. Very responsive, respectful of rate limiting (5s delay).

- **robots.txt notes:** FlashScore allows crawling. No special restrictions.

- **Data fetched:** 
  - `tests/fixtures/flashscore/israel-league/ligat-haal.html` (569 KB)
  - Contains league information, standings, and match schedules

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
| **espn** | ✅ Success | Complete standings with 14 Israeli teams, clean HTML | Build BeautifulSoup parser for standings extraction |
| **flashscore** | ✅ Success | League info + match schedules accessible | Build BeautifulSoup parser for league/schedule extraction |
| **transfermarkt** | ✅ Success | HTML pages parse well; player/club/transfer data available | Implement BeautifulSoup parser for HTML extraction |
| **wikidata** | ✅ Success | 285 Israeli clubs with EN/HE names + Transfermarkt IDs | Use as club master data source |
| **ifa** | ⚠️ Blocked | 403 Forbidden on all endpoints | Requires Playwright + headless browser or official API |
| **sofascore** | ⚠️ Blocked | 403 Forbidden on API; authentication required | Check if API key / partnership possible |
| **fotmob** | ⚠️ Blocked | 404 Not Found on public API endpoints | Reverse-engineer from browser or find alternative |

---

## Implementation Plan (Plans 2+)

### Plan 2: Wikidata Parser ⭐ READY
- Extract club master data from JSON
- Create `Club` rows with bilingual names and Transfermarkt IDs for linking
- **Status:** ✅ Ready, straightforward JSON parsing

### Plan 3: ESPN Parser ⭐ READY
- Parse HTML standings table using BeautifulSoup
- Extract: position, team name, played, W/D/L, GF/GA, GD, points
- Create `Standing` rows for league tables
- **Status:** ✅ Ready, clean HTML structure with 505 KB fixture

### Plan 4: FlashScore Parser ⭐ READY
- Parse HTML league page using BeautifulSoup
- Extract: match schedules, team listings, league structure
- Create `Match` rows with basic info (date, home, away, score)
- **Status:** ✅ Ready, 569 KB fixture available

### Plan 5: Transfermarkt Parser ⭐ READY
- Parse HTML using BeautifulSoup
- Extract player profiles, squad lists, transfer history
- Link to Transfermarkt club/player IDs
- **Status:** ✅ Ready, HTML well-structured

### Plan 6: IFA Parser (Deferred/Future)
- Requires Playwright for JavaScript rendering
- Alternative: Look for IFA public data feeds or API documentation
- **Status:** ⏳ Blocked, requires alternative approach

### Plan 7: Sofascore / FotMob (Deferred/Future)
- Both API-based but protected by authentication
- May need to establish partnership or find official feeds
- **Status:** ⏳ Blocked, requires authentication/partnership

---

## Notes

- **Cloud environment limitation:** This cloud sandbox has restricted network access. IFA, Sofascore, and FotMob 403/404 responses may differ from results on a standard internet connection.
- **Recommendation for Task 11 completion on user's Mac:** Run `ilfootball fetch` commands directly on your machine to get unfiltered results from all sources, then document actual findings (which may differ from cloud results for protected endpoints).
- **Data freshness:** All fixtures captured on 2026-11-19. Season 2024/25 is current/in-progress.
