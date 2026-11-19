"""Data-quality checks over the canonical tables. Each returns a list of Issues."""
from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Issue:
    check: str
    match_id: str
    detail: str


_SCORE_SQL = """
WITH goals AS (
    SELECT e.match_id,
        SUM(CASE WHEN (e.type IN ('goal','pen_goal') AND e.club_id = m.home_club_id)
                   OR (e.type = 'own_goal' AND e.club_id = m.away_club_id) THEN 1 ELSE 0 END) AS home,
        SUM(CASE WHEN (e.type IN ('goal','pen_goal') AND e.club_id = m.away_club_id)
                   OR (e.type = 'own_goal' AND e.club_id = m.home_club_id) THEN 1 ELSE 0 END) AS away
    FROM event e JOIN match m USING (match_id)
    GROUP BY e.match_id
)
SELECT m.match_id, m.home_goals, m.away_goals, COALESCE(g.home, 0), COALESCE(g.away, 0)
FROM match m LEFT JOIN goals g USING (match_id)
WHERE m.status = 'played'
  AND m.match_id IN (SELECT match_id FROM event)
  AND (m.home_goals <> COALESCE(g.home, 0) OR m.away_goals <> COALESCE(g.away, 0))
ORDER BY m.match_id
"""

_STARTERS_SQL = """
SELECT match_id, club_id, COUNT(*) FILTER (WHERE is_starter) AS starters
FROM lineup
GROUP BY match_id, club_id
HAVING starters <> 11
ORDER BY match_id, club_id
"""


def check_score_matches_events(con: duckdb.DuckDBPyConnection) -> list[Issue]:
    return [
        Issue("score_vs_events", mid, f"score {hg}-{ag} but events give {eh}-{ea}")
        for mid, hg, ag, eh, ea in con.execute(_SCORE_SQL).fetchall()
    ]


def check_eleven_starters(con: duckdb.DuckDBPyConnection) -> list[Issue]:
    return [
        Issue("eleven_starters", mid, f"club {club} has {n} starters")
        for mid, club, n in con.execute(_STARTERS_SQL).fetchall()
    ]


ALL_CHECKS = (check_score_matches_events, check_eleven_starters)


def run_all(con: duckdb.DuckDBPyConnection) -> list[Issue]:
    return [issue for check in ALL_CHECKS for issue in check(con)]
