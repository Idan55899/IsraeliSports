"""Open the DuckDB database and make sure the canonical schema exists."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import duckdb


def init_db(path: Path | str) -> duckdb.DuckDBPyConnection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(files("ilfootball.db").joinpath("schema.sql").read_text(encoding="utf-8"))
    return con
