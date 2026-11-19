from ilfootball.cli import main
from ilfootball.db.connect import init_db
from ilfootball.load.upsert import upsert
from ilfootball.models import Match, MatchEvent


def test_init_db_creates_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    assert main(["init-db"]) == 0
    assert (tmp_path / "ilfootball.duckdb").exists()
    assert "database ready" in capsys.readouterr().out


def test_check_clean_db_exits_zero(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    assert main(["check"]) == 0
    assert "0 issue(s)" in capsys.readouterr().out


def test_check_reports_issue_and_exits_one(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    con = init_db(tmp_path / "ilfootball.duckdb")
    upsert(con, [
        Match(match_id="ma-1", season_id="se-1", home_club_id="H", away_club_id="A",
              home_goals=1, away_goals=0, status="played"),
        MatchEvent(event_id="e1", match_id="ma-1", minute=5, club_id="A", type="goal"),
    ])
    con.close()
    assert main(["check"]) == 1
    assert "[score_vs_events] ma-1: score 1-0 but events give 0-1" in capsys.readouterr().out
