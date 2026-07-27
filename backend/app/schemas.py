"""
Pydantic schemas — define the JSON shape returned by our API endpoints.

Why separate from models.py? models.py describes our DATABASE tables (internal).
schemas.py describes our API RESPONSES (external, client-facing).
"""

from datetime import datetime
from pydantic import BaseModel


class DriverOut(BaseModel):
    driver_number: int
    full_name: str
    team_name: str
    team_colour: str | None = None

    class Config:
        from_attributes = True


class StandingOut(BaseModel):
    """One row in the live standings table — a driver's current position + gap."""
    driver_number: int
    full_name: str
    team_name: str
    team_colour: str | None = None
    position: int | None = None
    gap_to_leader: float | None = None
    interval: float | None = None


class LapOut(BaseModel):
    driver_number: int
    lap_number: int
    lap_duration: float | None = None
    is_pit_out_lap: bool


class PitStopOut(BaseModel):
    driver_number: int
    lap_number: int
    pit_duration: float | None = None
    date: datetime


class SessionOut(BaseModel):
    id: int
    session_key: int
    session_name: str
    country_name: str
    circuit_short_name: str
    year: int
    date_start: datetime

    class Config:
        from_attributes = True