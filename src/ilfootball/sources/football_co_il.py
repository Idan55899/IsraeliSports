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

    Uses div-based structure with 'current-round-details-row' class.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    matches = []

    # Find match row containers
    match_rows = soup.find_all('div', class_='current-round-details-row')

    for row in match_rows:
        try:
            # Extract team IDs from data attribute (e.g., "4548 4632")
            data_team = row.get('data-team', '')
            team_ids = data_team.split()
            if len(team_ids) < 2:
                continue

            away_team_id, home_team_id = team_ids[0], team_ids[1]

            # Extract date and time from data attributes
            date_str = row.get('data-date', '')  # Format: "18-08-26"

            # Extract date, day, time, teams, score from labels
            labels = row.find_all('label', class_='current-round-details-row-label')

            if len(labels) < 5:
                continue

            # Labels order: date, day, time, team names (in one label with hyphen), score
            date_text = labels[0].get_text(strip=True)  # e.g., "18.08.26"
            day_text = labels[1].get_text(strip=True)   # e.g., "שלישי"
            time_text = labels[2].get_text(strip=True)   # e.g., "19:30"
            teams_text = labels[3].get_text(strip=True)  # e.g., "הפועל עפולה - מ.ס. אשדוד"
            score_text = labels[4].get_text(strip=True) if len(labels) > 4 else ""

            # Extract team names from "TeamA - TeamB" format
            team_names = teams_text.split(' - ')
            if len(team_names) < 2:
                continue

            home_name = team_names[0].strip()
            away_name = team_names[1].strip()

            if not home_name or not away_name:
                continue

            # Parse score "X - Y" format
            home_goals = away_goals = None
            if score_text and ' - ' in score_text:
                parts = score_text.split(' - ')
                try:
                    home_goals = int(parts[0].strip())
                    away_goals = int(parts[1].strip()) if len(parts) > 1 else None
                except ValueError:
                    pass

            # Parse date and time
            kickoff_utc = None
            if date_text and time_text:
                try:
                    # Format is "18.08.26 19:30" -> interpret as "26.08.18 19:30" or based on date format
                    date_parts = date_text.split('.')
                    if len(date_parts) == 3:
                        # Try "DD.MM.YY" format first
                        try:
                            parsed = datetime.strptime(f"{date_parts[0]}.{date_parts[1]}.20{date_parts[2]} {time_text}", "%d.%m.%Y %H:%M")
                            kickoff_utc = parsed
                        except ValueError:
                            pass
                except Exception:
                    pass

            # Create canonical IDs
            home_id = f"cl-football-co-il-{home_name.lower().replace(' ', '-').replace("'", '').replace('/', '-')}"
            away_id = f"cl-football-co-il-{away_name.lower().replace(' ', '-').replace("'", '').replace('/', '-')}"
            match_id = f"ma-football-co-il-{home_team_id}-{away_team_id}-{int(kickoff_utc.timestamp()) if kickoff_utc else 0}"

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
