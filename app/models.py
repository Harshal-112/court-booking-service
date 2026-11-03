from datetime import datetime
from decimal import Decimal
from datetime import time
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from app.database import Base


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint(
            "role IN ('member', 'staff')",
            name="ck_members_valid_role",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
        server_default="member",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

def validate_operating_hours(
    opening_time: str,
    closing_time: str,
) -> None:
    try:
        opening = time.fromisoformat(opening_time)
        closing = time.fromisoformat(closing_time)
    except ValueError:
        raise ValueError(
            "Operating hours must use valid HH:MM format."
        )

    if opening >= closing:
        raise ValueError(
            "Opening time must be earlier than closing time."
        )

class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint(
            "opening_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_venues_valid_opening_time",
        ),
        CheckConstraint(
            "closing_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_venues_valid_closing_time",
        ),
        CheckConstraint(
            "opening_time < closing_time",
            name="ck_venues_opening_before_closing",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    opening_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="06:00",
    )

    closing_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="22:00",
    )

    base_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=500.00,
        server_default="500.00",
    )

    peak_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=750.00,
        server_default="750.00",
    )

    peak_start_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="18:00",
    )

    peak_end_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="22:00",
    )

    def __init__(self, **kwargs):
        opening = kwargs.get("opening_time", "06:00")
        closing = kwargs.get("closing_time", "22:00")

        kwargs.setdefault("opening_time", opening)
        kwargs.setdefault("closing_time", closing)

        opening_time = time.fromisoformat(opening)
        closing_time = time.fromisoformat(closing)

        default_peak_start = max(
            opening_time,
            time(18, 0),
        )

        if default_peak_start >= closing_time:
            default_peak_start = opening_time

        kwargs.setdefault(
            "peak_start_time",
            default_peak_start.strftime("%H:%M"),
        )
        kwargs.setdefault("peak_end_time", closing)

        super().__init__(**kwargs)

    @validates(
        "opening_time",
        "closing_time",
        "peak_start_time",
        "peak_end_time",
    )
    def validate_venue_hours(self, key, value):
        from datetime import time

        try:
            parsed_value = time.fromisoformat(value)

            if parsed_value.tzinfo is not None:
                raise ValueError

            if len(value) != 5:
                raise ValueError

        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid {key}. Expected HH:MM format."
            )

        opening = (
            value if key == "opening_time"
            else self.opening_time
        )

        closing = (
            value if key == "closing_time"
            else self.closing_time
        )

        peak_start = (
            value if key == "peak_start_time"
            else self.peak_start_time
        )

        peak_end = (
            value if key == "peak_end_time"
            else self.peak_end_time
        )

        if opening and closing:
            validate_operating_hours(opening, closing)

        if peak_start and peak_end:
            if time.fromisoformat(peak_start) >= time.fromisoformat(peak_end):
                raise ValueError(
                    "Peak start time must be earlier than peak end time."
                )
        if opening and closing and peak_start and peak_end:
            opening_time = time.fromisoformat(opening)
            closing_time = time.fromisoformat(closing)
            peak_start_time = time.fromisoformat(peak_start)
            peak_end_time = time.fromisoformat(peak_end)

            if (
                peak_start_time < opening_time
                or peak_end_time > closing_time
            ):
                raise ValueError(
                    "Peak hours must fall within venue operating hours."
                )
        return value
    courts: Mapped[list["Court"]] = relationship(
        back_populates="venue",
    )

class Court(Base):
    __tablename__ = "courts"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)

    venue: Mapped["Venue"] = relationship(back_populates="courts")


class Hold(Base):
    __tablename__ = "holds"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
        index=True,
    )
    court_id: Mapped[int] = mapped_column(
        ForeignKey("courts.id"),
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
        index=True,
    )
    court_id: Mapped[int] = mapped_column(
        ForeignKey("courts.id"),
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="confirmed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )



class CourtReservation(Base):
    __tablename__ = "court_reservations"

    __table_args__ = (
        ExcludeConstraint(
            ("court_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            name="ex_court_reservations_no_overlap",
            using="gist",
            where=text("status IN ('held', 'confirmed')"),
        ),
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_court_reservations_positive_duration",
        ),
        CheckConstraint(
            "status IN ('held', 'confirmed', 'cancelled', 'expired')",
            name="ck_court_reservations_valid_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
        index=True,
    )

    court_id: Mapped[int] = mapped_column(
        ForeignKey("courts.id"),
        nullable=False,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=500.00,
        server_default="500.00",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    refund_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
