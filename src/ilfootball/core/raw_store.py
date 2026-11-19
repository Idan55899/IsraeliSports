"""Immutable, gzip-compressed cache of every downloaded response."""
from __future__ import annotations

import gzip
import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(part: str) -> str:
    cleaned = _SAFE.sub("_", part).strip("._")
    if not cleaned:
        raise ValueError(f"unusable path part: {part!r}")
    return cleaned


class RawStore:
    def __init__(self, base: Path) -> None:
        self.base = Path(base)

    def path_for(self, source: str, entity: str, key: str, ext: str) -> Path:
        return self.base / _safe(source) / _safe(entity) / f"{_safe(key)}.{_safe(ext)}.gz"

    def exists(self, source: str, entity: str, key: str, ext: str) -> bool:
        return self.path_for(source, entity, key, ext).exists()

    def save(self, source: str, entity: str, key: str, ext: str, content: bytes) -> Path:
        path = self.path_for(source, entity, key, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(gzip.compress(content))
        tmp.replace(path)
        return path

    def load(self, source: str, entity: str, key: str, ext: str) -> bytes:
        return gzip.decompress(self.path_for(source, entity, key, ext).read_bytes())
