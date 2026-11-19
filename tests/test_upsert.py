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
