"""
Creates the 'stints' table and adds sector-time columns to 'laps' directly,
without going through Alembic. Use this if the migration step was skipped
and you're hitting `relation "stints" does not exist`.

Run with: python fix_missing_tire_schema.py

Safe to re-run — every statement uses IF NOT EXISTS.
"""

import asyncio
from sqlalchemy import text

from app.database import AsyncSessionLocal

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS stints (
        id SERIAL PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        driver_number INTEGER NOT NULL,
        stint_number INTEGER NOT NULL,
        compound VARCHAR(20) NOT NULL,
        lap_start INTEGER,
        lap_end INTEGER,
        tyre_age_at_start INTEGER,
        CONSTRAINT uq_stint_per_driver UNIQUE (session_id, driver_number, stint_number)
    );
    """,
    "ALTER TABLE laps ADD COLUMN IF NOT EXISTS duration_sector_1 FLOAT;",
    "ALTER TABLE laps ADD COLUMN IF NOT EXISTS duration_sector_2 FLOAT;",
    "ALTER TABLE laps ADD COLUMN IF NOT EXISTS duration_sector_3 FLOAT;",
]


async def main():
    async with AsyncSessionLocal() as db:
        for stmt in STATEMENTS:
            await db.execute(text(stmt))
        await db.commit()
    print("Schema fixed: 'stints' table created, sector columns added to 'laps'.")


if __name__ == "__main__":
    asyncio.run(main())