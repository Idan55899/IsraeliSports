"""Parse ESPN HTML for Israeli football standings and fixtures."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from ilfootball.models import Competition, Season, Standing


def parse_standings_html(content: bytes) -> tuple[Competition, Season, Iterable[Standing]]:
    """Extract standings from ESPN HTML table.

    Returns: (competition, season, standings_rows)
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    # Create competition (Israeli Premier League)
    competition = Competition(
        competition_id="co-espn-isr1",
        name_en="Ligat Ha'Al",
        name_he="ליגת העל",
        type="league",
        tier=1,
    )

    # Create season (2024/25)
    season = Season(
        season_id="se-espn-2024-25",
        competition_id=competition.competition_id,
        label="2024/25",
        start_date=date(2024, 8, 1),
        end_date=date(2025, 5, 31),
    )

    standings = []

    # Find the main standings table
    table = soup.find('table')
    if not table:
        return competition, season, standings

    tbody = table.find('tbody')
    if not tbody:
        return competition, season, standings

    rows = tbody.find_all('tr')

    for position, row in enumerate(rows, 1):
        cells = row.find_all('td')
        if len(cells) < 7:  # Need at least: pos, team, played, W, D, L, pts
            continue

        # Extract team name (usually in second or third cell)
        team_name_cell = None
        for cell in cells[1:3]:  # Check a few cells for team name
            text = cell.get_text(strip=True)
            if text and len(text) > 2 and not text.isdigit():
                team_name_cell = text
                break

        if not team_name_cell:
            continue

        # Try to extract stats (position, played, wins, draws, losses, points)
        try:
            # Look for numeric columns
            stats_text = []
            for cell in cells:
                text = cell.get_text(strip=True)
                if text and text.isdigit():
                    stats_text.append(int(text))

            # Expected order: position, played, W, D, L, GF, GA, GD, points
            if len(stats_text) >= 5:
                # Fallback to position from row order if not found
                pos_in_table = position
                played = stats_text[0] if stats_text[0] < 100 else stats_text[1]

                # Find W/D/L/GF/GA/points
                # This is fragile; better approach would be to analyze header row
                # For now, just extract what we can
                if len(stats_text) >= 8:
                    # Likely: position, played, W, D, L, GF, GA, GD, points (or similar)
                    wins = stats_text[1] if stats_text[1] < 50 else None
                    points = stats_text[-1] if stats_text[-1] < 150 else None
                else:
                    wins = None
                    points = None

                # Create canonical club ID from team name
                club_id = f"cl-espn-{team_name_cell.lower().replace(' ', '-')}"

                standing = Standing(
                    season_id=season.season_id,
                    round=1,  # Would need to parse round from page context
                    club_id=club_id,
                    position=pos_in_table,
                    played=played,
                    won=wins,
                    points=points,
                )
                standings.append(standing)
        except (ValueError, IndexError):
            continue

    return competition, season, standings
