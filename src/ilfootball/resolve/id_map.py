"""Map each source's ids to one canonical id per real-world entity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
from rapidfuzz import fuzz

from ilfootball.resolve.normalize import name_key

PREFIX = {"player": "pl", "club": "cl", "match": "ma", "competition": "co", "season": "se", "coach": "ch"}
FUZZY_THRESHOLD = 90.0


@dataclass(frozen=True)
class Candidate:
    canonical_id: str
    name: str
    birth_date: date | None = None


class IdMap:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con

    def lookup(self, entity_type: str, source: str, source_id: str) -> str | None:
        row = self.con.execute(
            "SELECT canonical_id FROM id_map WHERE entity_type=? AND source=? AND source_id=?",
            [entity_type, source, source_id],
        ).fetchone()
        return row[0] if row else None

    def register(
        self, entity_type: str, source: str, source_id: str, canonical_id: str,
        source_name: str | None = None, confidence: float = 1.0, method: str = "manual",
    ) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO id_map VALUES (?, ?, ?, ?, ?, ?, ?)",
            [entity_type, source, source_id, canonical_id, source_name, confidence, method],
        )

    def mint(self, entity_type: str, source: str, source_id: str, source_name: str | None = None) -> str:
        """Create a new canonical id, derived from the first source that saw the entity."""
        canonical_id = f"{PREFIX[entity_type]}-{source}-{source_id}"
        self.register(entity_type, source, source_id, canonical_id, source_name, 1.0, "minted")
        return canonical_id

    def resolve_player(
        self, source: str, source_id: str, name: str, birth_date: date | None,
        candidates: list[Candidate],
    ) -> str:
        """Known id -> exact DOB+name -> fuzzy name (+DOB) -> mint a new player."""
        known = self.lookup("player", source, source_id)
        if known:
            return known
        key = name_key(name)
        best: tuple[float, Candidate] | None = None
        for cand in candidates:
            if birth_date and cand.birth_date and birth_date != cand.birth_date:
                continue
            score = fuzz.token_sort_ratio(key, name_key(cand.name))
            if best is None or score > best[0]:
                best = (score, cand)
        if best:
            score, cand = best
            same_dob = birth_date is not None and birth_date == cand.birth_date
            if score == 100.0 and same_dob:
                self.register("player", source, source_id, cand.canonical_id, name, 1.0, "exact_dob_name")
                return cand.canonical_id
            if score >= FUZZY_THRESHOLD and same_dob:
                self.register("player", source, source_id, cand.canonical_id, name, score / 100, "fuzzy_dob_name")
                return cand.canonical_id
        return self.mint("player", source, source_id, name)
