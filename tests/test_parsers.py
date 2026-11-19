"""Test HTML/JSON parsers for Israeli football sources."""
from pathlib import Path

from ilfootball.sources.football_co_il import parse_matches_html
from ilfootball.sources.transfermarkt import parse_clubs_index_html, parse_squad_html
from ilfootball.sources.wikidata import parse_clubs_json


def test_wikidata_parser():
    """Test Wikidata club parser."""
    fixture = Path(__file__).parent / "fixtures" / "wikidata" / "clubs" / "israel.json"
    content = fixture.read_bytes()

    clubs = list(parse_clubs_json(content))

    assert len(clubs) > 100
    assert all(c.club_id.startswith("cl-wikidata-") for c in clubs)
    assert all(c.name_en for c in clubs)


def test_transfermarkt_clubs_index():
    """Test Transfermarkt clubs index parser."""
    fixture = Path(__file__).parent / "fixtures" / "transfermarkt" / "clubs" / "israel.html"
    content = fixture.read_bytes()

    clubs = list(parse_clubs_index_html(content))

    # Should extract some clubs
    assert len(clubs) > 0
    assert all(c.club_id.startswith("cl-transfermarkt-") for c in clubs)
    assert all(c.name_en for c in clubs)


def test_transfermarkt_squad():
    """Test Transfermarkt squad parser."""
    fixture = Path(__file__).parent / "fixtures" / "transfermarkt" / "squad" / "maccabi-haifa.html"
    content = fixture.read_bytes()

    players = list(parse_squad_html(content, "Maccabi Haifa"))

    # Should extract some players
    assert len(players) > 0
    assert all(p.player_id.startswith("pl-transfermarkt-") for p in players)
    assert all(p.name_en for p in players)


def test_football_co_il_matches():
    """Test football.co.il matches parser."""
    fixture = Path(__file__).parent / "fixtures" / "football_co_il" / "all_scores.html"
    if not fixture.exists():
        return  # Skip if fixture not available

    content = fixture.read_bytes()
    matches = list(parse_matches_html(content))

    # Should extract some matches (56 game elements expected)
    assert len(matches) > 0
    assert all(m.match_id.startswith("ma-football-co-il-") for m in matches)
    assert all(m.home_club_id for m in matches)
    assert all(m.away_club_id for m in matches)
