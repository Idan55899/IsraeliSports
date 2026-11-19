"""Name normalisation for matching the same person/club across sources."""
from __future__ import annotations

import re
import unicodedata

_NIQQUD = re.compile(r"[֑-ׇ]")
_FINAL_LETTERS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_DROP = re.compile(r"[׳״'\"`’‘”“.]")
_SEPARATORS = re.compile(r"[-_/,()]+")
_SPACES = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase, strip accents/niqqud/punctuation, unify Hebrew final letters."""
    text = _NIQQUD.sub("", name)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.translate(_FINAL_LETTERS)
    text = _DROP.sub("", text)
    text = _SEPARATORS.sub(" ", text)
    return _SPACES.sub(" ", text).strip().lower()


def name_key(name: str) -> str:
    """Order-insensitive key: 'Zahavi Eran' and 'Eran Zahavi' give the same key."""
    return " ".join(sorted(normalize_name(name).split()))
