from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Court, CourtReservation, Member


HOLD_DURATION = timedelta(minutes=5)
SLOT_DURATION = timedelta(hours=1)
MAX_ACTIVE_RESERVATIONS = 3
PEAK_START = time(18, 0)
PEAK_END = time(22, 0)

class ReservationError(Exception):
    """Base exception for reservation-related errors."""


class MemberNotFoundError(ReservationError):
    pass


class CourtNotFoundError(ReservationError):
    pass


class BookingConflictError(ReservationError):
    pass


class InvalidBookingTimeError(ReservationError):
    pass


class HoldNotFoundError(ReservationError):
    pass


class HoldExpiredError(ReservationError):
    pass


class BookingNotFoundError(ReservationError):
    pass


class BookingCancellationError(ReservationError):
    pass

def create_hold(
    session: Session,
    member_id: int,
    court_id: int,
    starts_at: datetime,
) -> CourtReservation:
    """Create a temporary hold for a one-hour court slot."""

    now = datetime.now(timezone.utc)

    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise InvalidBookingTimeError(
            "Booking time must include a timezone."
        )

    if starts_at <= now:
        raise InvalidBookingTimeError(
            "Booking must start in the future."
        )

    try:
        with session.begin():
            # Serialize reservation requests from the same member.
            member = session.scalar(
                select(Member)
                .where(Member.id == member_id)
                .with_for_update()
            )

            if member is None:
                raise MemberNotFoundError("Member not found.")

            # Serialize changes for this court.
            court = session.scalar(
                select(Court)
                .where(Court.id == court_id)
                .with_for_update()
            )
            if court is None:
                raise CourtNotFoundError("Court not found.")
            
            venue = court.venue

            venue_timezone = ZoneInfo(venue.timezone)
            local_start = starts_at.astimezone(venue_timezone)

            booking_time = local_start.timetz().replace(tzinfo=None)

            if PEAK_START <= booking_time < PEAK_END:
                booking_price = venue.peak_price
            else:
                booking_price = venue.base_price

            # Release expired holds for this court.
            session.execute(
                update(CourtReservation)
                .where(
                    CourtReservation.court_id == court_id,
                    CourtReservation.status == "held",
                    CourtReservation.expires_at <= now,
                )
                .values(status="expired")
            )

            # Count future confirmed bookings and unexpired holds.
            active_count = session.scalar(
                select(func.count(CourtReservation.id)).where(
                    CourtReservation.member_id == member_id,
                    CourtReservation.starts_at > now,
                    or_(
                        CourtReservation.status == "confirmed",
                        and_(
                            CourtReservation.status == "held",
                            CourtReservation.expires_at > now,
                        ),
                    ),
                )
            )

            if (active_count or 0) >= MAX_ACTIVE_RESERVATIONS:
                raise BookingConflictError(
                    "Member already has 3 active future reservations."
                )

            reservation = CourtReservation(
                member_id=member_id,
                court_id=court_id,
                starts_at=starts_at,
                ends_at=starts_at + SLOT_DURATION,
                expires_at=now + HOLD_DURATION,
                status="held",
                price=booking_price,
            )

            session.add(reservation)
            session.flush()

    except IntegrityError as exc:
        # PostgreSQL SQLSTATE 23P01 means exclusion constraint violation.
        if getattr(exc.orig, "sqlstate", None) == "23P01":
            raise BookingConflictError(
                "This court is already reserved for that time."
            ) from exc

        raise

    return reservation



def confirm_hold(
    session: Session,
    hold_id: int,
) -> CourtReservation:
    """Confirm an active hold."""

    now = datetime.now(timezone.utc)
    hold_expired = False

    with session.begin():
        reservation = session.scalar(
            select(CourtReservation)
            .where(CourtReservation.id == hold_id)
            .with_for_update()
        )

        if reservation is None:
            raise HoldNotFoundError("Hold not found.")

        if reservation.status == "confirmed":
            # Retry of an already successful confirmation.
            pass

        elif reservation.status != "held":
            raise HoldExpiredError("Hold is no longer active.")

        elif reservation.expires_at is None or reservation.expires_at <= now:
            reservation.status = "expired"
            hold_expired = True

        else:
            reservation.status = "confirmed"
            reservation.expires_at = None

        session.flush()

    # Raise only after the transaction commits.
    if hold_expired:
        raise HoldExpiredError("Hold has expired.")

    return reservation


def cancel_booking(
    session: Session,
    booking_id: int,
) -> CourtReservation:
    """Cancel a confirmed reservation and calculate refund eligibility."""

    now = datetime.now(timezone.utc)

    with session.begin():
        reservation = session.scalar(
            select(CourtReservation)
            .where(CourtReservation.id == booking_id)
            .with_for_update()
        )

        if reservation is None:
            raise BookingNotFoundError("Booking not found.")

        if reservation.status == "cancelled":
            # Repeated cancellation returns the existing result.
            return reservation

        if reservation.status != "confirmed":
            raise BookingCancellationError(
                "Only confirmed bookings can be cancelled."
            )

        reservation.status = "cancelled"
        reservation.cancelled_at = now

        # Full refund eligibility if cancellation is at least 24 hours early.
        reservation.refund_eligible = (
            reservation.starts_at - now >= timedelta(hours=24)
        )

        session.flush()

    return reservation


def get_court_availability(
    session: Session,
    court_id: int,
    requested_date: date,
) -> list[dict]:
    # 1. Fetch court and its venue.
    court = session.scalar(
        select(Court).where(Court.id == court_id)
    )

    if court is None:
        raise CourtNotFoundError("Court not found.")

    venue = court.venue

    # 2. Convert venue operating hours into timezone-aware datetimes.
    venue_timezone = ZoneInfo(venue.timezone)

    opening_time = time.fromisoformat(venue.opening_time)
    closing_time = time.fromisoformat(venue.closing_time)

    if closing_time <= opening_time:
        raise ValueError("Invalid venue operating hours.")

    opening_datetime = datetime.combine(
        requested_date,
        opening_time,
        tzinfo=venue_timezone,
    )

    closing_datetime = datetime.combine(
        requested_date,
        closing_time,
        tzinfo=venue_timezone,
    )

    # 3. Generate one-hour slots.
    slots = []
    current_slot = opening_datetime

    while current_slot + SLOT_DURATION <= closing_datetime:
        slot_end = current_slot + SLOT_DURATION

        slots.append({
            "starts_at": current_slot,
            "ends_at": slot_end,
            "available": True,
        })

        current_slot = slot_end

    # 4. Fetch active reservations for this court and date.
    now = datetime.now(timezone.utc)

    day_start_utc = opening_datetime.astimezone(timezone.utc)
    day_end_utc = closing_datetime.astimezone(timezone.utc)

    reservations = session.scalars(
        select(CourtReservation).where(
            CourtReservation.court_id == court_id,
            CourtReservation.status.in_(["held", "confirmed"]),
            CourtReservation.starts_at < day_end_utc,
            CourtReservation.ends_at > day_start_utc,
            or_(
                CourtReservation.status == "confirmed",
                and_(
                    CourtReservation.status == "held",
                    CourtReservation.expires_at > now,
                ),
            ),
        )
    ).all()

    # 5. Mark overlapping slots unavailable.
    for slot in slots:
        for reservation in reservations:
            if (
                slot["starts_at"] < reservation.ends_at
                and slot["ends_at"] > reservation.starts_at
            ):
                slot["available"] = False
                break

    return slots
