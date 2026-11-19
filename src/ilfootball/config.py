"""Runtime settings, read from environment variables with safe defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_AGENT = "ilfootball-dataset/0.1 (personal research project)"

# Minimum seconds between requests to the same host.
DEFAULT_HOST_INTERVALS: dict[str, float] = {
    "www.football.org.il": 3.0,
    "www.transfermarkt.com": 6.0,
    "www.sofascore.com": 4.0,
    "www.fotmob.com": 4.0,
    "query.wikidata.org": 1.0,
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    user_agent: str = DEFAULT_USER_AGENT
    default_interval: float = 5.0
    host_intervals: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_HOST_INTERVALS))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ilfootball.duckdb"

    def interval_for(self, host: str) -> float:
        return self.host_intervals.get(host, self.default_interval)


def load_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("ILF_DATA_DIR", "data")),
        user_agent=os.environ.get("ILF_USER_AGENT", DEFAULT_USER_AGENT),
    )
