"""
FastAPI app — exposes the F1 data in Postgres over HTTP.

Endpoints:
  GET /sessions                         -> list all sessions we have data for
  GET /sessions/{session_id}/drivers    -> drivers in a session
  GET /sessions/{session_id}/standings  -> live standings (position + gaps combined)
  GET /sessions/{session_id}/laps       -> lap times for a session
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models import Session as SessionModel, Driver, Position, Interval, Lap
from app.schemas import SessionOut, DriverOut, StandingOut, LapOut
from app.ingestion import poll_session
from app.standings import get_season_scoring_rows, aggregate_drivers, aggregate_constructors
from app.models import Stint, Pitstop as PitstopModel

app = FastAPI(title="F1 Live Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracks which sessions currently have a live poller running,
# so we don't accidentally start the same poller twice.
_active_pollers: set[int] = set()

@app.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SessionModel).order_by(SessionModel.date_start.desc()))
    return result.scalars().all()


@app.get("/sessions/{session_id}/drivers", response_model=list[DriverOut])
async def get_drivers(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Driver).where(Driver.session_id == session_id)
    )
    drivers = result.scalars().all()
    if not drivers:
        raise HTTPException(status_code=404, detail="No drivers found for this session")
    return drivers


@app.get("/sessions/{session_id}/standings", response_model=list[StandingOut])
async def get_standings(session_id: int, db: AsyncSession = Depends(get_db)):
    """
    Combines each driver's latest position and latest interval snapshot into
    one row per driver — this is the query the live dashboard polls repeatedly.
    """
    latest_position_subq = (
        select(
            Position.driver_number,
            func.max(Position.recorded_at).label("latest_time"),
        )
        .where(Position.session_id == session_id)
        .group_by(Position.driver_number)
        .subquery()
    )

    latest_interval_subq = (
        select(
            Interval.driver_number,
            func.max(Interval.recorded_at).label("latest_time"),
        )
        .where(Interval.session_id == session_id)
        .group_by(Interval.driver_number)
        .subquery()
    )

    stmt = (
        select(
            Driver.driver_number,
            Driver.full_name,
            Driver.team_name,
            Driver.team_colour,
            Position.position,
            Interval.gap_to_leader,
            Interval.interval,
        )
        .select_from(Driver)
        .where(Driver.session_id == session_id)
        .outerjoin(
            latest_position_subq,
            Driver.driver_number == latest_position_subq.c.driver_number,
        )
        .outerjoin(
            Position,
            (Position.driver_number == latest_position_subq.c.driver_number)
            & (Position.recorded_at == latest_position_subq.c.latest_time)
            & (Position.session_id == session_id),
        )
        .outerjoin(
            latest_interval_subq,
            Driver.driver_number == latest_interval_subq.c.driver_number,
        )
        .outerjoin(
            Interval,
            (Interval.driver_number == latest_interval_subq.c.driver_number)
            & (Interval.recorded_at == latest_interval_subq.c.latest_time)
            & (Interval.session_id == session_id),
        )
        .order_by(Position.position.asc().nulls_last())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        StandingOut(
            driver_number=row.driver_number,
            full_name=row.full_name,
            team_name=row.team_name,
            team_colour=row.team_colour,
            position=row.position,
            gap_to_leader=row.gap_to_leader,
            interval=row.interval,
        )
        for row in rows
    ]

@app.get("/sessions/{session_id}/laps-detailed")
async def get_laps_detailed(session_id: int, db: AsyncSession = Depends(get_db)):
    """
    Lap times including per-sector splits and a pit-in flag, for the Laps
    tab's expanded view (sector times + pit in/out icons).
    """
    laps_result = await db.execute(
        select(Lap)
        .where(Lap.session_id == session_id)
        .order_by(Lap.driver_number, Lap.lap_number)
    )
    laps = laps_result.scalars().all()

    pit_result = await db.execute(
        select(PitstopModel.driver_number, PitstopModel.lap_number)
        .where(PitstopModel.session_id == session_id)
    )
    pit_in_laps = {(row.driver_number, row.lap_number) for row in pit_result.all()}

    return [
        {
            "driver_number": lap.driver_number,
            "lap_number": lap.lap_number,
            "lap_duration": lap.lap_duration,
            "duration_sector_1": lap.duration_sector_1,
            "duration_sector_2": lap.duration_sector_2,
            "duration_sector_3": lap.duration_sector_3,
            "is_pit_out_lap": lap.is_pit_out_lap,
            "is_pit_in_lap": (lap.driver_number, lap.lap_number) in pit_in_laps,
        }
        for lap in laps
    ]


@app.get("/sessions/{session_id}/stints")
async def get_stints(session_id: int, db: AsyncSession = Depends(get_db)):
    """Full tire stint history for a session — one row per compound run per driver."""
    result = await db.execute(
        select(Stint)
        .where(Stint.session_id == session_id)
        .order_by(Stint.driver_number, Stint.stint_number)
    )
    stints = result.scalars().all()
    return [
        {
            "driver_number": s.driver_number,
            "stint_number": s.stint_number,
            "compound": s.compound,
            "lap_start": s.lap_start,
            "lap_end": s.lap_end,
            "tyre_age_at_start": s.tyre_age_at_start,
        }
        for s in stints
    ]


@app.get("/sessions/{session_id}/current-tyres")
async def get_current_tyres(session_id: int, db: AsyncSession = Depends(get_db)):
    """Each driver's current (highest stint_number) compound — for a Tyre column on Standings."""
    result = await db.execute(
        select(Stint)
        .where(Stint.session_id == session_id)
        .order_by(Stint.driver_number, Stint.stint_number.desc())
    )
    stints = result.scalars().all()

    latest_by_driver: dict[int, Stint] = {}
    for s in stints:
        if s.driver_number not in latest_by_driver:
            latest_by_driver[s.driver_number] = s

    return [
        {
            "driver_number": s.driver_number,
            "compound": s.compound,
            "tyre_age_at_start": s.tyre_age_at_start,
            "stint_number": s.stint_number,
        }
        for s in latest_by_driver.values()
    ]


@app.get("/sessions/{session_id}/laps", response_model=list[LapOut])
async def get_laps(session_id: int, driver_number: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Lap).where(Lap.session_id == session_id)
    if driver_number is not None:
        stmt = stmt.where(Lap.driver_number == driver_number)
    stmt = stmt.order_by(Lap.driver_number, Lap.lap_number)

    result = await db.execute(stmt)
    return result.scalars().all()

@app.get("/standings/drivers")
async def drivers_championship(year: int = 2026, db: AsyncSession = Depends(get_db)):
    """
    Full-season Drivers' Championship standings, computed from every
    seeded Race session's final classification. Works entirely from
    already-seeded data — no live ingestion required.
    """
    rows = await get_season_scoring_rows(db, year)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No completed race results found for {year}. Run the season seed script first.",
        )
    return {"year": year, "standings": aggregate_drivers(rows)}


@app.get("/standings/constructors")
async def constructors_championship(year: int = 2026, db: AsyncSession = Depends(get_db)):
    """
    Full-season Constructors' Championship standings — same underlying
    race results as /standings/drivers, grouped by team instead of driver.
    """
    rows = await get_season_scoring_rows(db, year)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No completed race results found for {year}. Run the season seed script first.",
        )
    return {"year": year, "standings": aggregate_constructors(rows)}


@app.post("/sessions/{session_id}/start-live")
async def start_live_ingestion(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Starts polling OpenF1 for this session in the background.
    Intended to be called during an actual live F1 session — practice,
    qualifying, or race — since that's the only time OpenF1's endpoints
    return genuinely live (not historical) data.
    """
    if session_id in _active_pollers:
        return {"status": "already running", "session_id": session_id}

    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    _active_pollers.add(session_id)
    background_tasks.add_task(
        poll_session, AsyncSessionLocal, session_id, session.session_key
    )

    return {"status": "started", "session_id": session_id, "session_key": session.session_key}


@app.get("/next-race")
async def next_race():
    """
    Returns the next scheduled F1 session, and the most recently completed race,
    by checking OpenF1's session list directly (not our own database, since we
    only store sessions we've explicitly seeded).
    """
    import httpx
    from datetime import datetime, timezone

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.openf1.org/v1/sessions", params={"year": 2026})
        resp.raise_for_status()
        all_sessions = resp.json()

    now = datetime.now(timezone.utc)

    upcoming = [
        s for s in all_sessions
        if datetime.fromisoformat(s["date_start"]) > now
    ]
    past = [
        s for s in all_sessions
        if datetime.fromisoformat(s["date_start"]) <= now
    ]

    upcoming.sort(key=lambda s: s["date_start"])
    past.sort(key=lambda s: s["date_start"], reverse=True)

    next_session = upcoming[0] if upcoming else None
    last_race = next(
        (s for s in past if s["session_name"] == "Race"), None
    )

    return {
        "next_session": next_session,
        "last_race": last_race,
    }

@app.get("/sessions/by-key/{session_key}/standings")
async def standings_by_openf1_key(session_key: int):
    """
    Fetches final standings for ANY OpenF1 session_key directly from OpenF1,
    even if we haven't seeded it into our own database. Used for showing
    the last race's results on the landing page without requiring a seed first.
    """
    import httpx
    from app.ingestion import _parse_ts

    async with httpx.AsyncClient(timeout=15) as client:
        drivers_resp = await client.get(
            "https://api.openf1.org/v1/drivers", params={"session_key": session_key}
        )
        drivers_resp.raise_for_status()
        drivers = drivers_resp.json()

        positions_resp = await client.get(
            "https://api.openf1.org/v1/position", params={"session_key": session_key}
        )
        positions_resp.raise_for_status()
        positions = positions_resp.json()

    # Keep only each driver's LAST reported position (the final result)
    latest_position = {}
    for p in positions:
        dn = p["driver_number"]
        if dn not in latest_position or p["date"] > latest_position[dn]["date"]:
            latest_position[dn] = p

    driver_lookup = {d["driver_number"]: d for d in drivers}

    results = []
    for dn, pos_row in latest_position.items():
        d = driver_lookup.get(dn, {})
        results.append({
            "driver_number": dn,
            "full_name": d.get("full_name", "Unknown"),
            "team_name": d.get("team_name", "Unknown"),
            "team_colour": d.get("team_colour"),
            "position": pos_row["position"],
        })

    results.sort(key=lambda r: r["position"] if r["position"] is not None else 999)
    return results