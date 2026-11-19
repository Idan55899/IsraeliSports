"""Parse Wikidata SPARQL results for Israeli football clubs."""
from __future__ import annotations

import json
from typing import Iterable

from ilfootball.models import Club


def parse_clubs_json(content: bytes) -> Iterable[Club]:
    """Extract club data from Wikidata SPARQL JSON response.

    Expected format: SPARQL JSON with bindings containing:
    - club: entity URI (e.g., http://www.wikidata.org/entity/Q206585)
    - en: English label
    - he: Hebrew label
    - tm: Transfermarkt ID (optional)
    """
    data = json.loads(content.decode('utf-8'))
    bindings = data.get('results', {}).get('bindings', [])

    seen_ids = set()

    for binding in bindings:
        # Extract club ID from URI
        club_uri = binding.get('club', {}).get('value', '')
        wikidata_id = club_uri.split('/')[-1] if club_uri else None

        if not wikidata_id or wikidata_id in seen_ids:
            continue
        seen_ids.add(wikidata_id)

        # Extract names
        name_en = binding.get('en', {}).get('value')
        name_he = binding.get('he', {}).get('value')
        tm_id = binding.get('tm', {}).get('value')

        # Skip if no English name
        if not name_en:
            continue

        # Create canonical club ID
        club_id = f"cl-wikidata-{wikidata_id}"

        yield Club(
            club_id=club_id,
            name_en=name_en,
            name_he=name_he,
            wikidata_qid=wikidata_id,
        )
