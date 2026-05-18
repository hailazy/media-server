"""Cost ledger (SQLite). One row per CLI invocation, attributed by --project.

The reason a single shared tool beats N hand-rolled clients on a *paid* API:
one place to see spend across consumers.

    sqlite3 data/ledger.db \\
      "select project,count(*),round(sum(est_cost),4) from calls group by project"
"""

from __future__ import annotations

import time

from .cache import _connect


def _db():
    con = _connect("ledger.db")
    con.execute(
        "CREATE TABLE IF NOT EXISTS calls ("
        "ts REAL, provider TEXT, model TEXT, quality TEXT, size TEXT, "
        "n INTEGER, project TEXT, est_cost REAL, cache_hit INTEGER)"
    )
    return con


def record(
    *,
    provider: str,
    model: str,
    quality: str,
    size: str,
    n: int,
    project: str,
    est_cost: float,
    cache_hit: bool,
) -> None:
    con = _db()
    try:
        con.execute(
            "INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?)",
            (
                time.time(),
                provider,
                model,
                quality,
                size,
                n,
                project or "",
                0.0 if cache_hit else est_cost,
                int(cache_hit),
            ),
        )
        con.commit()
    finally:
        con.close()
