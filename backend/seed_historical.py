"""
One-off script: fetches a real historical F1 session from OpenF1 and writes
it into our Postgres tables. This proves the schema + ingestion logic work
against real data, without needing to wait for a live race weekend.

Run with: python seed_historical.py
"""

import asyncio
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal
from app.models import Session as SessionModel, Driver, Position, Lap, Pitstop, Interval
from app.ingestion import upsert_positions, upsert_intervals, _parse_ts

OPENF1_BASE = "https://api.openf1.org/v1"

TARGET_YEAR = 2024
TARGET_COUNTRY = "United Arab Emirates"
TARGET_SESSION_NAME = "Race"


async def fetch_json(client: httpx.AsyncClient, path: str, params: dict) -> list[dict]:
    resp = await client.get(f"{OPENF1_BASE}/{path}", params=params)
    resp.raise_for_status()
    return resp.json()


async def seed():
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: find the session
        sessions = await fetch_json(
            client, "sessions",
            {"year": TARGET_YEAR, "country_name": TARGET_COUNTRY, "session_name": TARGET_SESSION_NAME},
        )
        if not sessions:
            print("No matching session found — check year/country/session_name.")
            return

        session_data = sessions[0]
        session_key = session_data["session_key"]
        print(f"Found session_key={session_key}: {session_data['session_name']} "
              f"at {session_data['circuit_short_name']} ({session_data['year']})")

        async with AsyncSessionLocal() as db:
            # Step 2: insert the Session row
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

            # Fetch our internal session id (not OpenF1's session_key) for foreign keys
            result = await db.execute(
                select(SessionModel.id).where(SessionModel.session_key == session_key)
            )
            internal_session_id = result.scalar_one()
            await db.commit()  # close the autobegun transaction from the SELECT above
            print(f"Internal session id: {internal_session_id}")

            # Step 3: drivers
            drivers = await fetch_json(client, "drivers", {"session_key": session_key})
            print(f"Fetched {len(drivers)} driver entries")
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
                    stmt = pg_insert(Driver).values(values)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=["session_id", "driver_number"]
                    )
                    await db.execute(stmt)

            # Step 4: positions (reusing the exact upsert function from ingestion.py)
            positions = await fetch_json(client, "position", {"session_key": session_key})
            print(f"Fetched {len(positions)} position snapshots")
            await upsert_positions(db, internal_session_id, positions)

            # Step 5: intervals
            intervals = await fetch_json(client, "intervals", {"session_key": session_key})
            print(f"Fetched {len(intervals)} interval snapshots")
            await upsert_intervals(db, internal_session_id, intervals)

            # Step 6: laps
            laps = await fetch_json(client, "laps", {"session_key": session_key})
            print(f"Fetched {len(laps)} lap records")
            if laps:
                async with db.begin():
                    values = [
                        {
                            "session_id": internal_session_id,
                            "driver_number": l["driver_number"],
                            "lap_number": l["lap_number"],
                            "lap_duration": l.get("lap_duration"),
                            "date_start": _parse_ts(l.get("date_start")),
                            "is_pit_out_lap": l.get("is_pit_out_lap", False),
                        }
                        for l in laps
                        if l.get("date_start") is not None
                    ]
                    if values:
                        stmt = pg_insert(Lap).values(values)
                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=["session_id", "driver_number", "lap_number"]
                        )
                        await db.execute(stmt)

            # Step 7: pit stops (note: OpenF1's endpoint is called "pit", not "pit_stops")
            pit_stops = await fetch_json(client, "pit", {"session_key": session_key})
            print(f"Fetched {len(pit_stops)} pit stop records")
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

        print("\nSeeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())