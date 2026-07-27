"""
FastAPI app — exposes the F1 data in Postgres over HTTP.

Endpoints:
  GET /sessions                         -> list all sessions we have data for
  GET /sessions/{session_id}/drivers    -> drivers in a session
  GET /sessions/{session_id}/standings  -> live standings (position + gaps combined)
  GET /sessions/{session_id}/laps       -> lap times for a session
"""

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Session as SessionModel, Driver, Position, Interval, Lap
from app.schemas import SessionOut, DriverOut, StandingOut, LapOut

app = FastAPI(title="F1 Live Dashboard API")


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


@app.get("/sessions/{session_id}/laps", response_model=list[LapOut])
async def get_laps(session_id: int, driver_number: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Lap).where(Lap.session_id == session_id)
    if driver_number is not None:
        stmt = stmt.where(Lap.driver_number == driver_number)
    stmt = stmt.order_by(Lap.driver_number, Lap.lap_number)

    result = await db.execute(stmt)
    return result.scalars().all()