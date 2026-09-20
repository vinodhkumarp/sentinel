"""Reading RateRadar's run ledger.

Every piece of knowledge about RateRadar's tables lives in this file and nowhere
else. That is the whole design: supporting a second pipeline later means writing
a sibling of this module, not touching the classifier (ADR-0002).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..db import Conn
from ..model import Run, UnitHistory, UnitRun

_RUN_COLUMNS = """
    run_id, status, started_at, finished_at, "trigger", git_sha,
    brands_total, brands_ok, brands_failed
"""


def _to_run(row: dict[str, Any]) -> Run:
    return Run(
        run_id=row["run_id"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        trigger=row["trigger"],
        code_version=row["git_sha"],
        units_total=row["brands_total"],
        units_ok=row["brands_ok"],
        units_failed=row["brands_failed"],
    )


def fetch_run(conn: Conn, run_id: int) -> Run | None:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_RUN_COLUMNS} FROM collection_run WHERE run_id = %s", (run_id,))
        row = cur.fetchone()
    return _to_run(row) if row else None


def fetch_latest_run(conn: Conn, *, trigger: str | None = None) -> Run | None:
    """The most recent run that actually finished.

    A run still in flight has half its units recorded, and classifying that
    would report every unit yet to be reached as missing.
    """
    sql = f"SELECT {_RUN_COLUMNS} FROM collection_run WHERE status <> 'running'"
    params: list[Any] = []
    if trigger:
        sql += ' AND "trigger" = %s'
        params.append(trigger)
    sql += " ORDER BY run_id DESC LIMIT 1"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return _to_run(row) if row else None


def fetch_units(conn: Conn, run_id: int) -> list[UnitRun]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rb.run_id, rb.brand_id, b.brand_name, rb.status, rb.api_version,
                   rb.products_seen, rb.products_failed, rb.products_quarantined,
                   rb.snapshots_new, rb.http_requests, rb.duration_ms,
                   rb.error_kind, rb.error_detail
            FROM collection_run_brand rb
            JOIN brand b USING (brand_id)
            WHERE rb.run_id = %s
            ORDER BY b.brand_name
            """,
            (run_id,),
        )
        rows = cur.fetchall()

    return [
        UnitRun(
            run_id=r["run_id"],
            unit_id=r["brand_id"],
            unit_name=r["brand_name"],
            status=r["status"],
            items_seen=r["products_seen"],
            items_failed=r["products_failed"],
            items_quarantined=r["products_quarantined"],
            items_new=r["snapshots_new"],
            requests=r["http_requests"],
            duration_ms=r["duration_ms"],
            error_kind=r["error_kind"],
            error_detail=r["error_detail"],
            protocol_version=r["api_version"],
        )
        for r in rows
    ]


def fetch_histories(
    conn: Conn, run_id: int, unit_ids: list[str], *, limit: int = 10
) -> dict[str, UnitHistory]:
    """What each unit did in the runs before this one, newest first.

    Fetches a bounded window for all units in one query and slices per unit in
    Python: at twenty brands and ten runs that is two hundred rows, and a window
    function here would buy nothing but a harder query to read.
    """
    if not unit_ids:
        return {}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rb.brand_id, rb.run_id, rb.status, rb.products_seen, rb.api_version
            FROM collection_run_brand rb
            JOIN collection_run r USING (run_id)
            WHERE rb.run_id < %s
              AND rb.brand_id = ANY(%s)
              AND r.status <> 'running'
            ORDER BY rb.brand_id, rb.run_id DESC
            """,
            (run_id, unit_ids),
        )
        rows = cur.fetchall()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = grouped[row["brand_id"]]
        if len(bucket) < limit:
            bucket.append(row)

    histories: dict[str, UnitHistory] = {}
    for unit_id in unit_ids:
        bucket = grouped.get(unit_id, [])
        previous_version = next(
            (r["api_version"] for r in bucket if r["api_version"] is not None), None
        )
        histories[unit_id] = UnitHistory(
            unit_id=unit_id,
            recent_statuses=tuple(r["status"] for r in bucket),
            recent_items_seen=tuple(r["products_seen"] for r in bucket),
            previous_protocol_version=previous_version,
        )
    return histories
