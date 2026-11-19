"""Parse football.co.il (official Israeli Football Association) HTML."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from ilfootball.models import Competition, Match, Season, Standing


def parse_standings_html(content: bytes) -> Iterable[Standing]:
    """Extract league standings from football.co.il standings page.

    Expected: League table with teams, position, W/D/L, GF/GA, points.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    # Find standings table
    table = soup.find('table')
    if not table:
        return []

    standings = []
    tbody = table.find('tbody')
    if not tbody:
        return standings

    rows = tbody.find_all('tr')

    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 7:  # Need: pos, team, played, W, D, L, pts
            continue

        try:
            # Try to extract position from first cell
            pos_text = cells[0].get_text(strip=True)
            if not pos_text.isdigit():
                continue

            position = int(pos_text)

            # Extract team name (usually in second cell)
            team_name = cells[1].get_text(strip=True)
            if not team_name:
                continue

            # Extract stats (need to identify which columns are which)
            stats_cells = [c.get_text(strip=True) for c in cells[2:]]
            stats = [s for s in stats_cells if s.isdigit()]

            if len(stats) < 4:
                continue

            # Assuming: played, wins, draws, losses, GF, GA, GD, points
            played = int(stats[0]) if len(stats) > 0 else None
            won = int(stats[1]) if len(stats) > 1 else None
            drawn = int(stats[2]) if len(stats) > 2 else None
            lost = int(stats[3]) if len(stats) > 3 else None
            goals_for = int(stats[4]) if len(stats) > 4 else None
            goals_against = int(stats[5]) if len(stats) > 5 else None
            points = int(stats[-1]) if len(stats) > 0 else None

            # Create canonical club ID from team name
            club_id = f"cl-football-co-il-{team_name.lower().replace(' ', '-')}"

            standing = Standing(
                season_id="se-football-co-il-2024-25",  # Will vary by page
                round=1,  # Need to parse from page context
                club_id=club_id,
                position=position,
                played=played,
                won=won,
                drawn=drawn,
                lost=lost,
                goals_for=goals_for,
                goals_against=goals_against,
                points=points,
            )
            standings.append(standing)

        except (ValueError, IndexError):
            continue

    return standings


def parse_matches_html(content: bytes) -> Iterable[Match]:
    """Extract match results from football.co.il matches page.

    Expected: Match list with home/away teams, scores, dates.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    matches = []

    # Find match containers (structure varies, may need adjustment)
    match_elements = soup.find_all('div', class_='match')  # or similar

    for elem in match_elements:
        try:
            # Extract match info
            # This is a template - exact selectors depend on page structure
            home = elem.find(class_='home-team')
            away = elem.find(class_='away-team')

            if not home or not away:
                continue

            home_name = home.get_text(strip=True)
            away_name = away.get_text(strip=True)

            # Extract score
            score_elem = elem.find(class_='score')
            if score_elem:
                score_text = score_elem.get_text(strip=True)
                # Parse "X-Y" format
                parts = score_text.split('-')
                home_goals = int(parts[0].strip()) if len(parts) > 0 else None
                away_goals = int(parts[1].strip()) if len(parts) > 1 else None
            else:
                home_goals = away_goals = None

            # Extract date
            date_elem = elem.find(class_='date')
            kickoff_utc = None
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                try:
                    # Try to parse various date formats
                    for fmt in ('%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d'):
                        try:
                            kickoff_utc = datetime.strptime(date_text, fmt)
                            break
                        except ValueError:
                            continue
                except:
                    pass

            # Create canonical IDs
            home_id = f"cl-football-co-il-{home_name.lower().replace(' ', '-')}"
            away_id = f"cl-football-co-il-{away_name.lower().replace(' ', '-')}"
            match_id = f"ma-football-co-il-{home_name[:3].lower()}-{away_name[:3].lower()}-{kickoff_utc.timestamp() if kickoff_utc else 0}"

            match = Match(
                match_id=match_id,
                season_id="se-football-co-il-2024-25",
                home_club_id=home_id,
                away_club_id=away_id,
                home_goals=home_goals,
                away_goals=away_goals,
                kickoff_utc=kickoff_utc,
                status="played" if home_goals is not None else "scheduled",
            )
            matches.append(match)

        except Exception:
            continue

    return matches


def parse_teams_html(content: bytes) -> Iterable[tuple[str, str]]:
    """Extract team list from football.co.il teams page.

    Returns: (team_id, team_name) tuples
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    teams = []

    # Find team elements
    team_elements = soup.find_all('div', class_='team')  # or similar

    for elem in team_elements:
        try:
            name_elem = elem.find(class_='team-name')
            if name_elem:
                team_name = name_elem.get_text(strip=True)
                team_id = f"cl-football-co-il-{team_name.lower().replace(' ', '-')}"
                teams.append((team_id, team_name))
        except:
            continue

    return teams
