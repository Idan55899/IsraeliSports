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
