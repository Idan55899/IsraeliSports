"""End-to-end data loading for Israeli football from all sources."""
from __future__ import annotations

from pathlib import Path

import duckdb

from ilfootball.load.upsert import upsert
from ilfootball.resolve.id_map import IdMap
from ilfootball.sources.espn import parse_standings_html
from ilfootball.sources.football_co_il import parse_matches_html
from ilfootball.sources.transfermarkt import parse_clubs_index_html, parse_squad_html
from ilfootball.sources.wikidata import parse_clubs_json


def load_from_fixtures(con: duckdb.DuckDBPyConnection, fixtures_dir: Path | str = "tests/fixtures") -> dict[str, int]:
    """Load Israeli football data from local fixtures.

    Returns count of rows loaded by source.
    """
    fixtures_dir = Path(fixtures_dir)
    counts = {}

    # Load Wikidata clubs (club master reference)
    print("\n📥 Loading Wikidata clubs...")
    wikidata_file = fixtures_dir / "wikidata" / "clubs" / "israel.json"
    if wikidata_file.exists():
        content = wikidata_file.read_bytes()
        clubs = list(parse_clubs_json(content))
        counts['wikidata_clubs'] = upsert(con, clubs)
        print(f"   ✓ Loaded {counts['wikidata_clubs']} clubs")
    else:
        print(f"   ⚠️  Fixture not found: {wikidata_file}")

    # Load Transfermarkt clubs index
    print("\n📥 Loading Transfermarkt clubs...")
    tm_clubs_file = fixtures_dir / "transfermarkt" / "clubs" / "israel.html"
    if tm_clubs_file.exists():
        content = tm_clubs_file.read_bytes()
        clubs = list(parse_clubs_index_html(content))
        counts['transfermarkt_clubs'] = upsert(con, clubs)
        print(f"   ✓ Loaded {counts['transfermarkt_clubs']} clubs")
    else:
        print(f"   ⚠️  Fixture not found: {tm_clubs_file}")

    # Load Transfermarkt squad (players)
    print("\n📥 Loading Transfermarkt players...")
    tm_squad_file = fixtures_dir / "transfermarkt" / "squad" / "maccabi-haifa.html"
    if tm_squad_file.exists():
        content = tm_squad_file.read_bytes()
        players = list(parse_squad_html(content, "Maccabi Haifa"))
        counts['transfermarkt_players'] = upsert(con, players)
        print(f"   ✓ Loaded {counts['transfermarkt_players']} players")
    else:
        print(f"   ⚠️  Fixture not found: {tm_squad_file}")

    # Load ESPN standings
    print("\n📥 Loading ESPN standings...")
    espn_file = fixtures_dir / "ESPN" / "standings" / "ligat-haal-2024-25.html"
    if espn_file.exists():
        content = espn_file.read_bytes()
        try:
            competition, season, standings = parse_standings_html(content)
            comp_count = upsert(con, [competition])
            season_count = upsert(con, [season])
            standings_count = upsert(con, standings)
            counts['espn_competition'] = comp_count
            counts['espn_season'] = season_count
            counts['espn_standings'] = standings_count
            print(f"   ✓ Loaded {comp_count} competition, {season_count} season, {standings_count} standings")
        except Exception as e:
            print(f"   ⚠️  Error parsing ESPN standings: {e}")
    else:
        print(f"   ⚠️  Fixture not found: {espn_file}")

    # Load Football.co.il matches
    print("\n📥 Loading Football.co.il matches...")
    football_co_il_files = [
        fixtures_dir / "football_co_il" / "all_scores.html",
        fixtures_dir / "football_co_il" / "team_scores.html",
    ]
    for fcil_file in football_co_il_files:
        if fcil_file.exists():
            content = fcil_file.read_bytes()
            try:
                matches = list(parse_matches_html(content))
                match_count = upsert(con, matches)
                key = f"football_co_il_matches_{fcil_file.stem}"
                counts[key] = match_count
                print(f"   ✓ Loaded {match_count} matches from {fcil_file.name}")
            except Exception as e:
                print(f"   ⚠️  Error parsing {fcil_file.name}: {e}")
        else:
            print(f"   ⚠️  Fixture not found: {fcil_file}")

    return counts


def show_loaded_data(con: duckdb.DuckDBPyConnection) -> None:
    """Display summary of loaded data."""
    print("\n" + "=" * 70)
    print("📊 LOADED DATA SUMMARY")
    print("=" * 70)

    tables = ["club", "player", "competition", "season", "standing", "match"]

    for table in tables:
        try:
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count > 0:
                print(f"\n{table.upper()}:")
                print(f"  Total rows: {count}")

                if table == "club" and count > 0:
                    # Show sample clubs
                    sample = con.execute(f"SELECT name_en, name_he FROM {table} LIMIT 3").fetchall()
                    for name_en, name_he in sample:
                        print(f"    - {name_en} ({name_he})")

                elif table == "player" and count > 0:
                    sample = con.execute(f"SELECT name_en, position FROM {table} LIMIT 3").fetchall()
                    for name, pos in sample:
                        print(f"    - {name} ({pos})")

                elif table == "standing" and count > 0:
                    sample = con.execute(
                        f"SELECT club_id, position, points FROM {table} LIMIT 3"
                    ).fetchall()
                    for club_id, pos, pts in sample:
                        print(f"    - {club_id}: Position {pos}, {pts} points")

                elif table == "match" and count > 0:
                    sample = con.execute(
                        f"SELECT home_club_id, away_club_id, home_goals, away_goals FROM {table} LIMIT 3"
                    ).fetchall()
                    for home, away, hg, ag in sample:
                        print(f"    - {home} {hg}-{ag} {away}")
        except duckdb.CatalogException:
            pass

    print("\n" + "=" * 70)
