"""Parse Transfermarkt HTML for Israeli football player and squad data."""
from __future__ import annotations

from datetime import date
from typing import Iterable

from ilfootball.models import Club, Player


def parse_clubs_index_html(content: bytes) -> Iterable[Club]:
    """Extract club list from Transfermarkt Israeli league index."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    # Find club links in the index
    # Transfermarkt structure typically has club links with /verein/ in the URL
    seen = set()

    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '/verein/' not in href:
            continue

        # Extract club ID from URL: .../verein/123/...
        try:
            parts = href.split('/')
            verein_idx = parts.index('verein')
            club_id_str = parts[verein_idx + 1]
            if not club_id_str.isdigit():
                continue

            if club_id_str in seen:
                continue
            seen.add(club_id_str)

            # Extract club name
            name = link.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            # Create canonical ID
            canonical_id = f"cl-transfermarkt-{club_id_str}"

            yield Club(
                club_id=canonical_id,
                name_en=name,
            )
        except (ValueError, IndexError):
            continue


def parse_squad_html(content: bytes, club_name: str = "") -> Iterable[Player]:
    """Extract player squad from Transfermarkt squad page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    # Find player rows in squad table
    # Transfermarkt squad pages have player info in table rows
    seen_players = set()

    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue

        # Try to find player link
        player_link = row.find('a', href=True)
        if not player_link or '/spieler/' not in player_link.get('href', ''):
            continue

        # Extract player ID from URL
        href = player_link.get('href', '')
        try:
            parts = href.split('/')
            spieler_idx = parts.index('spieler')
            player_id_str = parts[spieler_idx + 1]
            if not player_id_str.isdigit():
                continue

            if player_id_str in seen_players:
                continue
            seen_players.add(player_id_str)

            # Extract player name
            name = player_link.get_text(strip=True)
            if not name:
                continue

            # Try to extract additional info from cells
            # Typical columns: shirt#, name, position, age, nationality, etc.
            cell_texts = [c.get_text(strip=True) for c in cells]

            position = None
            nationality = None

            # Look for common position abbreviations
            for text in cell_texts:
                if text in ('FW', 'MF', 'DF', 'GK', 'Fw', 'Mf', 'Df', 'Gk'):
                    position = text.upper()
                    break

            # Create canonical ID
            canonical_id = f"pl-transfermarkt-{player_id_str}"

            yield Player(
                player_id=canonical_id,
                name_en=name,
                position=position,
                nationality=nationality,
            )
        except (ValueError, IndexError):
            continue


def parse_player_profile_html(content: bytes) -> Player | None:
    """Extract player details from Transfermarkt profile page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, 'html.parser')

    # Extract player name from page title or main heading
    name = None
    for heading in soup.find_all(['h1', 'h2']):
        text = heading.get_text(strip=True)
        if text:
            name = text
            break

    if not name:
        return None

    # Extract information from info boxes
    # Transfermarkt has "info-box" sections with player details
    birth_date = None
    nationality = None
    position = None
    height = None

    info_boxes = soup.find_all('div', class_='info-box')

    for box in info_boxes:
        # Look for label-value pairs
        for label in box.find_all(['strong', 'span']):
            label_text = label.get_text(strip=True).lower()
            value_elem = label.next_sibling
            if isinstance(value_elem, str):
                value = value_elem.strip()
            else:
                value = value_elem.get_text(strip=True) if value_elem else ""

            if 'date of birth' in label_text:
                # Try to parse date (format varies)
                try:
                    # Common formats: "Jan 1, 1990" or "01/01/1990"
                    from datetime import datetime
                    for fmt in ('%b %d, %Y', '%m/%d/%Y', '%d.%m.%Y'):
                        try:
                            birth_date = datetime.strptime(value, fmt).date()
                            break
                        except ValueError:
                            continue
                except:
                    pass

            elif 'nationality' in label_text or 'country' in label_text:
                nationality = value

            elif 'position' in label_text:
                position = value.upper()[:2]  # Usually 2-letter codes

            elif 'height' in label_text:
                height = value

    # Create canonical ID - would need to extract from URL
    canonical_id = f"pl-transfermarkt-unknown"

    return Player(
        player_id=canonical_id,
        name_en=name,
        birth_date=birth_date,
        nationality=nationality,
        position=position,
    )
