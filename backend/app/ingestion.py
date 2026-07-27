"""
Ingestion service: polls OpenF1 and writes into Postgres using UPSERT.

Key concepts in action here:
1. TRANSACTIONS  -> `async with db.begin():` wraps each batch write.
                     If any row fails, the whole batch rolls back.
2. TIMESTAMPTZ   -> OpenF1's ISO8601 timestamps are parsed directly into
                     timezone-aware Python datetimes.
3. UPSERT        -> pg_insert(...).on_conflict_do_update(...) makes
                     re-running the poller safe (idempotent) even after crashes.
"""

import asyncio
from datetime import datetime
import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Position, Interval

OPENF1_BASE = "https://api.openf1.org/v1"

# Respect OpenF1's free-tier rate limit: 3 req/s, 30 req/min.
POLL_INTERVAL_SECONDS = 4


def _parse_ts(value: str | None) -> datetime | None:
    """OpenF1 timestamps look like '2026-07-22T14:32:10.123000+00:00' — already tz-aware."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


async def fetch_positions(client: httpx.AsyncClient, session_key: int) -> list[dict]:
    resp = await client.get(f"{OPENF1_BASE}/position", params={"session_key": session_key})
    resp.raise_for_status()
    return resp.json()


async def fetch_intervals(client: httpx.AsyncClient, session_key: int) -> list[dict]:
    resp = await client.get(f"{OPENF1_BASE}/intervals", params={"session_key": session_key})
    resp.raise_for_status()
    return resp.json()


async def upsert_positions(db: AsyncSession, session_id: int, rows: list[dict]) -> None:
    if not rows:
        return

    values = [
        {
            "session_id": session_id,
            "driver_number": row["driver_number"],
            "position": row["position"],
            "recorded_at": _parse_ts(row["date"]),
        }
        for row in rows
        if row.get("date") is not None
    ]
    if not values:
        return

    stmt = pg_insert(Position).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["session_id", "driver_number", "recorded_at"],
        set_={"position": stmt.excluded.position},
    )

    async with db.begin():
        await db.execute(stmt)


async def upsert_intervals(db: AsyncSession, session_id: int, rows: list[dict]) -> None:
    if not rows:
        return

    values = [
        {
            "session_id": session_id,
            "driver_number": row["driver_number"],
            "gap_to_leader": row.get("gap_to_leader"),
            "interval": row.get("interval"),
            "recorded_at": _parse_ts(row["date"]),
        }
        for row in rows
        if row.get("date") is not None
    ]
    if not values:
        return

    stmt = pg_insert(Interval).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["session_id", "driver_number", "recorded_at"],
        set_={
            "gap_to_leader": stmt.excluded.gap_to_leader,
            "interval": stmt.excluded.interval,
        },
    )

    async with db.begin():
        await db.execute(stmt)


async def poll_session(db_session_factory, session_id: int, session_key: int) -> None:
    """
    Main polling loop for one live session. Runs as a background asyncio task
    for as long as the session is live.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                positions, intervals = await asyncio.gather(
                    fetch_positions(client, session_key),
                    fetch_intervals(client, session_key),
                )

                async with db_session_factory() as db:
                    await upsert_positions(db, session_id, positions)
                    await upsert_intervals(db, session_id, intervals)

            except httpx.HTTPError as e:
                print(f"[ingestion] OpenF1 request failed: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)