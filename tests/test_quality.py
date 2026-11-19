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
