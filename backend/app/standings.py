"""
Computes Drivers' and Constructors' Championship standings from race
results already sitting in the local DB — no live ingestion required.

Points follow the standard F1 system (P1-P10). Fastest-lap bonus point
is intentionally not included.
"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session as SessionModel, Driver, Position

POINTS_TABLE = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
SPRINT_POINTS_TABLE = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}


def _is_sprint_race(session_name: str) -> bool:
    """
    True for the actual sprint race (scores points), false for everything else
    including 'Sprint Qualifying' (sets the grid, scores nothing — same as
    regular qualifying). Matches by substring rather than an exact string
    since OpenF1's sprint naming has varied across seasons.
    """
    name = session_name.lower()
    return "sprint" in name and "qualifying" not in name and "shootout" not in name


async def _get_final_positions(db: AsyncSession, session_id: int) -> list[tuple[int, int]]:
    """Latest recorded position per driver for a given session — same
    'most recent snapshot' pattern used in main.py's /standings endpoint."""
    latest_position_subq = (
        select(
            Position.driver_number,
            func.max(Position.recorded_at).label("latest_time"),
        )
        .where(Position.session_id == session_id)
        .group_by(Position.driver_number)
        .subquery()
    )

    stmt = (
        select(Position.driver_number, Position.position)
        .join(
            latest_position_subq,
            (Position.driver_number == latest_position_subq.c.driver_number)
            & (Position.recorded_at == latest_position_subq.c.latest_time),
        )
        .where(Position.session_id == session_id)
    )

    result = await db.execute(stmt)
    return [(row.driver_number, row.position) for row in result.all() if row.position is not None]


async def get_season_scoring_rows(db: AsyncSession, year: int) -> list[dict]:
    """
    One row per driver per scoring session (Race or actual Sprint race —
    not Sprint Qualifying) they finished, across the given year. Used as
    the shared source for both the drivers' and constructors' championship
    endpoints.
    """
    sessions_result = await db.execute(
        select(SessionModel)
        .where(SessionModel.year == year)
        .order_by(SessionModel.date_start.asc())
    )
    all_sessions = sessions_result.scalars().all()
    scoring_sessions = [
        s for s in all_sessions
        if s.session_name == "Race" or _is_sprint_race(s.session_name)
    ]

    rows: list[dict] = []

    for session in scoring_sessions:
        is_sprint = session.session_name != "Race"
        points_table = SPRINT_POINTS_TABLE if is_sprint else POINTS_TABLE

        final_positions = await _get_final_positions(db, session.id)
        if not final_positions:
            continue  # session seeded but no position data yet (e.g. future race)

        drivers_result = await db.execute(select(Driver).where(Driver.session_id == session.id))
        drivers_by_number = {d.driver_number: d for d in drivers_result.scalars().all()}

        for driver_number, position in final_positions:
            driver = drivers_by_number.get(driver_number)
            if driver is None:
                continue
            rows.append({
                "driver_number": driver_number,
                "full_name": driver.full_name,
                "team_name": driver.team_name,
                "team_colour": driver.team_colour,
                "position": position,
                "points": points_table.get(position, 0),
                "session_id": session.id,
                "is_sprint": is_sprint,
            })

    return rows


def aggregate_drivers(rows: list[dict]) -> list[dict]:
    totals: dict[int, dict] = {}

    for row in rows:
        entry = totals.setdefault(row["driver_number"], {
            "driver_number": row["driver_number"],
            "full_name": row["full_name"],
            "team_name": row["team_name"],
            "team_colour": row["team_colour"],
            "points": 0,
            "wins": 0,
            "podiums": 0,
            "sprint_points": 0,
        })
        entry["points"] += row["points"]
        if row["is_sprint"]:
            entry["sprint_points"] += row["points"]
        # Always take the most recent race's name/team, in case of a mid-season swap
        entry["full_name"] = row["full_name"]
        entry["team_name"] = row["team_name"]
        entry["team_colour"] = row["team_colour"]
        # Wins/podiums are main-race-only stats, matching how F1 officially
        # reports them — a sprint win doesn't count as a "race win".
        if not row["is_sprint"]:
            if row["position"] == 1:
                entry["wins"] += 1
            if row["position"] <= 3:
                entry["podiums"] += 1

    standings = list(totals.values())
    standings.sort(key=lambda d: (-d["points"], -d["wins"], d["full_name"] or ""))
    for i, s in enumerate(standings, start=1):
        s["position"] = i

    return standings


def aggregate_constructors(rows: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}

    for row in rows:
        team_name = row["team_name"]
        entry = totals.setdefault(team_name, {
            "team_name": team_name,
            "team_colour": row["team_colour"],
            "points": 0,
            "wins": 0,
            "sprint_points": 0,
        })
        entry["points"] += row["points"]
        if row["is_sprint"]:
            entry["sprint_points"] += row["points"]
        if row["team_colour"]:
            entry["team_colour"] = row["team_colour"]
        if not row["is_sprint"] and row["position"] == 1:
            entry["wins"] += 1

    standings = list(totals.values())
    standings.sort(key=lambda t: (-t["points"], -t["wins"], t["team_name"] or ""))
    for i, s in enumerate(standings, start=1):
        s["position"] = i

    return standings