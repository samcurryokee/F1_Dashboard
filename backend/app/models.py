from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP

class Base(DeclarativeBase):
    pass


class Session(Base):

    '''
    A single F1 session: a practice, qualifying, sprint, or race.
    One race WEEKEND has multiple Sessions (FP1, FP2, FP3, Quali, Race).
    '''
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_key: Mapped[int] = mapped_column(unique=True)
    meeting_key: Mapped[int] = mapped_column(index=True)
    session_name: Mapped[str] = mapped_column(String(50))
    country_name: Mapped[str] = mapped_column(String(100))
    circuit_short_name: Mapped[str] = mapped_column(String(100))
    date_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    date_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    year: Mapped[int] = mapped_column(Integer, index=True)

    drivers: Mapped[list["Driver"]] = relationship(back_populates="session")

class Driver(Base):
    """
    A driver's participation in a specific session.
    (Same human driver gets a new row per session — simplest model to start with;
    we can normalize into a separate 'people' table later if needed.)
    """
    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", name="uq_driver_per_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    driver_number: Mapped[int]
    full_name: Mapped[str] = mapped_column(String(100))
    team_name: Mapped[str] = mapped_column(String(100))
    team_colour: Mapped[str | None] = mapped_column(String(10), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="drivers")



class Position(Base):
    """
    A driver's track position at a point in time.
    High-frequency table — this is the one that grows fastest.
    """
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", "recorded_at",
                          name="uq_position_snapshot"),
        Index("ix_positions_session_driver_time", "session_id", "driver_number", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    driver_number: Mapped[int]
    position: Mapped[int]
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Lap(Base):
    """One completed lap by one driver."""
    __tablename__ = "laps"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", "lap_number",
                          name="uq_lap_per_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    driver_number: Mapped[int]
    lap_number: Mapped[int]
    lap_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    is_pit_out_lap: Mapped[bool] = mapped_column(default=False)



class Pitstop(Base):
    """
    a pitstop event for a driver in a session. This is a separate table because pitstops are relatively rare events, and we want to avoid storing a lot of nulls in the Lap table.
    """
    __tablename__= "pit_stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    driver_number: Mapped[int]
    lap_number: Mapped[int]
    pit_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    date:Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

class Interval(Base):
    """
    Gap to the car ahead / gap to leader — this is what makes the dashboard feel 'live'.
    Also high-frequency, same upsert pattern as Position.
    """
    __tablename__ = "intervals"
    __table_args__ = (
        UniqueConstraint("session_id", "driver_number", "recorded_at",
                          name="uq_interval_snapshot"),
        Index("ix_intervals_session_driver_time", "session_id", "driver_number", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    driver_number: Mapped[int]
    gap_to_leader: Mapped[float | None] = mapped_column(Float, nullable=True)
    interval: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))