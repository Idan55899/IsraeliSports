"""Write typed rows into DuckDB, replacing rows that have the same primary key."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import duckdb

from ilfootball.models import Row


def upsert(con: duckdb.DuckDBPyConnection, rows: Iterable[Row]) -> int:
    by_table: dict[type[Row], list[Row]] = defaultdict(list)
    for row in rows:
        by_table[type(row)].append(row)
    written = 0
    for model, items in by_table.items():
        cols = list(model.model_fields)
        sql = (
            f"INSERT OR REPLACE INTO {model.table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})"
        )
        con.executemany(sql, [[getattr(r, c) for c in cols] for r in items])
        written += len(items)
    return written
