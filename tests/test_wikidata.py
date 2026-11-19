"""Test Wikidata parser."""
from pathlib import Path

from ilfootball.sources.wikidata import parse_clubs_json


def test_parse_clubs_json_from_fixture():
    """Parse real Wikidata fixture."""
    fixture = Path(__file__).parent / "fixtures" / "wikidata" / "clubs" / "israel.json"
    content = fixture.read_bytes()

    clubs = list(parse_clubs_json(content))

    # Should have many Israeli clubs
    assert len(clubs) > 100, f"Expected >100 clubs, got {len(clubs)}"

    # Check structure
    for club in clubs[:5]:
        assert club.club_id.startswith("cl-wikidata-")
        assert club.name_en, f"Missing English name for {club.club_id}"
        assert club.wikidata_qid, f"Missing Wikidata ID for {club.club_id}"

    # Should have bilingual names for major clubs
    major_clubs = [c for c in clubs if c.name_he]
    assert len(major_clubs) > 50, f"Expected >50 clubs with Hebrew names, got {len(major_clubs)}"

    # Check for specific clubs
    names_en = {c.name_en for c in clubs if c.name_en}
    assert any("Maccabi" in n or "Hapoel" in n for n in names_en), \
        "Expected to find major Israeli clubs"


def test_parse_clubs_no_duplicates():
    """Verify no duplicate Wikidata IDs."""
    fixture = Path(__file__).parent / "fixtures" / "wikidata" / "clubs" / "israel.json"
    content = fixture.read_bytes()

    clubs = list(parse_clubs_json(content))
    ids = [c.wikidata_qid for c in clubs]

    assert len(ids) == len(set(ids)), f"Found duplicate Wikidata IDs: {len(ids)} total, {len(set(ids))} unique"
