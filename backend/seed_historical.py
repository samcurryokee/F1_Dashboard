"""
Seeds the local database with Practice, Qualifying, and Race sessions
from the 2026 F1 season — sessions, drivers, positions, intervals, laps
(with sector times), pit stops, and tire stints.

Run with: python seed_season.py

Safe to re-run — every insert uses ON CONFLICT DO NOTHING, so already-
seeded sessions/rows are skipped rather than duplicated.

Each data type is fetched independently — a 404 or error on one endpoint
(e.g. OpenF1 has no /intervals data for Practice sessions, since gaps are
only meaningful in competitive Qualifying/Race) no longer aborts the rest
of that session's data. You'll see a per-endpoint note in the output when
something's unavailable rather than the whole session being skipped.
"""

import asyncio
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal
from app.models import Session as SessionModel, Driver, Lap, Pitstop, Stint
from app.ingestion import upsert_positions, upsert_intervals, _parse_ts

OPENF1_BASE = "https://api.openf1.org/v1"

TARGET_YEAR = 2026
BASE_SESSION_NAMES = {"Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"}

# Politeness delay between sessions — OpenF1 free tier allows 3 req/s / 30 req/min.
DELAY_BETWEEN_SESSIONS_SEC = 2.0


async def fetch_json(client: httpx.AsyncClient, path: str, params: dict) -> list[dict]:
    resp = await client.get(f"{OPENF1_BASE}/{path}", params=params)
    resp.raise_for_status()
    return resp.json()


async def safe_fetch_json(client: httpx.AsyncClient, path: str, params: dict, label: str) -> list[dict]:
    """
    Wraps fetch_json so a missing/erroring endpoint for this session
    (most commonly: no /intervals data for Practice sessions) doesn't
    take down the rest of that session's seeding.
    """
    try:
        return await fetch_json(client, path, params)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"    ({label}: not available for this session, skipping just this endpoint)")
        else:
            print(f"    ({label}: HTTP {e.response.status_code}, skipping just this endpoint)")
        return []
    except Exception as e:
        print(f"    ({label}: fetch failed — {e}, skipping just this endpoint)")
        return []


async def seed_one_session(client: httpx.AsyncClient, db, session_data: dict):
    session_key = session_data["session_key"]
    label = (
        f"{session_data['year']} {session_data['country_name']} — "
        f"{session_data['session_name']}"
    )

    # Session row
    async with db.begin():
        stmt = pg_insert(SessionModel).values(
            session_key=session_key,
            meeting_key=session_data["meeting_key"],
            session_name=session_data["session_name"],
            country_name=session_data["country_name"],
            circuit_short_name=session_data["circuit_short_name"],
            date_start=_parse_ts(session_data["date_start"]),
            date_end=_parse_ts(session_data.get("date_end")),
            year=session_data["year"],
        ).on_conflict_do_nothing(index_elements=["session_key"])
        await db.execute(stmt)

    result = await db.execute(
        select(SessionModel.id).where(SessionModel.session_key == session_key)
    )
    internal_session_id = result.scalar_one()
    await db.commit()

    # Drivers
    drivers = await safe_fetch_json(client, "drivers", {"session_key": session_key}, "drivers")
    if drivers:
        async with db.begin():
            values = [
                {
                    "session_id": internal_session_id,
                    "driver_number": d["driver_number"],
                    "full_name": d.get("full_name", "Unknown"),
                    "team_name": d.get("team_name", "Unknown"),
                    "team_colour": d.get("team_colour"),
                }
                for d in drivers
            ]
            stmt = pg_insert(Driver).values(values).on_conflict_do_nothing(
                index_elements=["session_id", "driver_number"]
            )
            await db.execute(stmt)

    # Positions
    positions = await safe_fetch_json(client, "position", {"session_key": session_key}, "positions")
    if positions:
        await upsert_positions(db, internal_session_id, positions)

    # Intervals — commonly unavailable for Practice sessions, that's expected
    intervals = await safe_fetch_json(client, "intervals", {"session_key": session_key}, "intervals")
    if intervals:
        await upsert_intervals(db, internal_session_id, intervals)

    # Laps — including sector times
    laps = await safe_fetch_json(client, "laps", {"session_key": session_key}, "laps")
    if laps:
        async with db.begin():
            values = [
                {
                    "session_id": internal_session_id,
                    "driver_number": l["driver_number"],
                    "lap_number": l["lap_number"],
                    "lap_duration": l.get("lap_duration"),
                    "duration_sector_1": l.get("duration_sector_1"),
                    "duration_sector_2": l.get("duration_sector_2"),
                    "duration_sector_3": l.get("duration_sector_3"),
                    "date_start": _parse_ts(l.get("date_start")),
                    "is_pit_out_lap": l.get("is_pit_out_lap", False),
                }
                for l in laps
                if l.get("date_start") is not None
            ]
            if values:
                stmt = pg_insert(Lap).values(values).on_conflict_do_nothing(
                    index_elements=["session_id", "driver_number", "lap_number"]
                )
                await db.execute(stmt)

    # Pit stops
    pit_stops = await safe_fetch_json(client, "pit", {"session_key": session_key}, "pit stops")
    if pit_stops:
        async with db.begin():
            values = [
                {
                    "session_id": internal_session_id,
                    "driver_number": p["driver_number"],
                    "lap_number": p["lap_number"],
                    "pit_duration": p.get("pit_duration"),
                    "date": _parse_ts(p.get("date")),
                }
                for p in pit_stops
                if p.get("date") is not None
            ]
            if values:
                stmt = pg_insert(Pitstop).values(values)
                await db.execute(stmt)

    # Tire stints
    stints = await safe_fetch_json(client, "stints", {"session_key": session_key}, "stints")
    if stints:
        async with db.begin():
            values = [
                {
                    "session_id": internal_session_id,
                    "driver_number": s["driver_number"],
                    "stint_number": s["stint_number"],
                    "compound": s.get("compound", "UNKNOWN"),
                    "lap_start": s.get("lap_start"),
                    "lap_end": s.get("lap_end"),
                    "tyre_age_at_start": s.get("tyre_age_at_start"),
                }
                for s in stints
            ]
            stmt = pg_insert(Stint).values(values).on_conflict_do_nothing(
                index_elements=["session_id", "driver_number", "stint_number"]
            )
            await db.execute(stmt)

    print(
        f"  {label}: {len(drivers)} drivers, {len(positions)} positions, "
        f"{len(intervals)} intervals, {len(laps)} laps, {len(pit_stops)} pit stops, "
        f"{len(stints)} stints"
    )


async def seed():
    async with httpx.AsyncClient(timeout=30) as client:
        all_sessions = await fetch_json(client, "sessions", {"year": TARGET_YEAR})

        # Discover any sprint-related session names actually present, rather than
        # guessing an exact string — OpenF1's naming has varied across seasons
        # (e.g. "Sprint" vs "Sprint Qualifying" vs "Sprint Shootout").
        discovered_names = {s["session_name"] for s in all_sessions}
        sprint_names = {n for n in discovered_names if "sprint" in n.lower()}
        session_names = BASE_SESSION_NAMES | sprint_names

        targets = [s for s in all_sessions if s["session_name"] in session_names]

        print(f"Found {len(targets)} matching sessions out of {len(all_sessions)} total for {TARGET_YEAR}.")
        print(f"Filtering to: {sorted(session_names)}")
        if sprint_names:
            print(f"  (sprint session names auto-detected: {sorted(sprint_names)})\n")
        else:
            print("  (no sprint sessions found for this year)\n")

        async with AsyncSessionLocal() as db:
            for i, session_data in enumerate(targets, start=1):
                print(f"[{i}/{len(targets)}] Seeding session_key={session_data['session_key']}...")
                try:
                    await seed_one_session(client, db, session_data)
                except Exception as e:
                    # Genuinely unexpected failure (not a per-endpoint 404,
                    # those are handled above) — log and keep going.
                    print(f"  Session-level error, skipped entirely: {e}")

                await asyncio.sleep(DELAY_BETWEEN_SESSIONS_SEC)

        print("\nSeason seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())