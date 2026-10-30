import pytest
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from zoneinfo import ZoneInfo

from app.services.reservation_service import InvalidBookingTimeError
from app.database import SessionLocal
from app.models import Member, Venue, Court, CourtReservation, validate_operating_hours
from app.services.reservation_service import create_hold
from app.services.reservation_service import BookingConflictError
from app.services.reservation_service import get_court_availability
from app.services.reservation_service import (
    confirm_hold,
    HoldNotFoundError,
    HoldExpiredError,
)

from app.services.reservation_service import cancel_booking
from app.services.reservation_service import BookingNotFoundError
from app.services.reservation_service import BookingCancellationError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from decimal import Decimal

def test_create_hold_success():
    # Arrange: Create test member, venue and court.
    with SessionLocal() as setup_session:
        member = Member(
            email=f"test_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    # Act: Create a hold using a fresh session.
    with SessionLocal() as session:
        start_time = datetime.now(timezone.utc) + timedelta(hours=2)

        reservation = create_hold(
            session=session,
            member_id=member_id,
            court_id=court_id,
            starts_at=start_time,
        )

        # Assert: Check the reservation details.
        assert reservation.id is not None
        assert reservation.status == "held"
        assert reservation.member_id == member_id
        assert reservation.court_id == court_id
        assert reservation.ends_at == start_time + timedelta(hours=1)
        assert reservation.expires_at is not None

def test_prevent_double_booking():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    with SessionLocal() as session:
        create_hold(session, member_id, court_id, start_time)

    with SessionLocal() as session:
        try:
            create_hold(session, member_id, court_id, start_time)
            assert False, "Expected BookingConflictError"
        except BookingConflictError:
            pass


def test_member_cannot_create_more_than_three_active_reservations():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    # Create three reservations at different time slots.
    for day in range(3):
        with SessionLocal() as session:
            create_hold(
                session,
                member_id,
                court_id,
                start_time + timedelta(days=day),
            )

    # Fourth reservation must be rejected.
    with SessionLocal() as session:
        try:
            create_hold(
                session,
                member_id,
                court_id,
                start_time + timedelta(days=3),
            )
            assert False, "Expected BookingConflictError"
        except BookingConflictError:
            pass


def test_reject_past_booking_time():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    with SessionLocal() as session:
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)

        try:
            create_hold(session, member_id, court_id, past_time)
            assert False, "Expected InvalidBookingTimeError"
        except InvalidBookingTimeError:
            pass


def test_reject_booking_without_timezone():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    with SessionLocal() as session:
        naive_time = datetime.now() + timedelta(hours=2)

        try:
            create_hold(session, member_id, court_id, naive_time)
            assert False, "Expected InvalidBookingTimeError"
        except InvalidBookingTimeError:
            pass


def test_expired_hold_does_not_block_slot():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    # Create the first hold.
    with SessionLocal() as session:
        first_hold = create_hold(
            session, member_id, court_id, start_time
        )
        first_hold_id = first_hold.id

    # Simulate expiration by setting expiry time in the past.
    with SessionLocal() as session:
        expired_hold = session.get(CourtReservation, first_hold_id)
        expired_hold.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    # Creating a new hold should expire the old one and succeed.
    with SessionLocal() as session:
        second_hold = create_hold(
            session, member_id, court_id, start_time
        )

        assert second_hold.status == "held"
        assert second_hold.id != first_hold_id

    # Verify the first hold was marked expired.
    with SessionLocal() as session:
        old_hold = session.get(CourtReservation, first_hold_id)
        assert old_hold.status == "expired"


def test_confirm_hold_success():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    with SessionLocal() as session:
        hold = create_hold(
            session, member_id, court_id, start_time
        )
        hold_id = hold.id

    with SessionLocal() as session:
        confirmed = confirm_hold(session, hold_id)

        assert confirmed.id == hold_id
        assert confirmed.status == "confirmed"
        assert confirmed.expires_at is None


def test_confirm_hold_is_idempotent():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    # First confirmation.
    with SessionLocal() as session:
        first_result = confirm_hold(session, hold_id)

    # Retry the same confirmation.
    with SessionLocal() as session:
        second_result = confirm_hold(session, hold_id)

    assert first_result.id == second_result.id
    assert first_result.status == "confirmed"
    assert second_result.status == "confirmed"

    # Verify only one reservation exists.
    with SessionLocal() as session:
        count = session.query(CourtReservation).filter_by(
            id=hold_id
        ).count()

        assert count == 1


def test_cannot_confirm_expired_hold():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    # Simulate expiration.
    with SessionLocal() as session:
        hold = session.get(CourtReservation, hold_id)
        hold.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    # Confirmation must fail.
    with SessionLocal() as session:
        try:
            confirm_hold(session, hold_id)
            assert False, "Expected HoldExpiredError"
        except HoldExpiredError:
            pass

    # Expired status must persist despite the exception.
    with SessionLocal() as session:
        hold = session.get(CourtReservation, hold_id)
        assert hold.status == "expired"


def test_confirm_nonexistent_hold():
    with SessionLocal() as session:
        try:
            confirm_hold(session, 999999)
            assert False, "Expected HoldNotFoundError"
        except HoldNotFoundError:
            pass


def test_concurrent_confirmation_is_idempotent():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    # Synchronize both confirmation requests.
    barrier = Barrier(2)

    def confirm_from_separate_session():
        with SessionLocal() as session:
            barrier.wait(timeout=10)
            result = confirm_hold(session, hold_id)
            return result.id, result.status

    # Execute both requests concurrently.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(confirm_from_separate_session)
        future_two = executor.submit(confirm_from_separate_session)

        result_one = future_one.result(timeout=15)
        result_two = future_two.result(timeout=15)

    # Both requests must return the same confirmed reservation.
    assert result_one == result_two
    assert result_one == (hold_id, "confirmed")

    with SessionLocal() as session:
        count = session.query(CourtReservation).filter_by(
            id=hold_id
        ).count()

        assert count == 1


def test_cancel_booking_with_full_refund_eligibility():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=48)

    # Create hold.
    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    # Confirm hold.
    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    # Cancel booking.
    with SessionLocal() as session:
        cancelled = cancel_booking(session, hold_id)

        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_at is not None
        assert cancelled.refund_eligible is True


def test_cancel_booking_without_full_refund_eligibility():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=12)

    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    with SessionLocal() as session:
        cancelled = cancel_booking(session, hold_id)

        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_at is not None
        assert cancelled.refund_eligible is False


def test_cancel_booking_is_idempotent():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=48)

    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    # First cancellation.
    with SessionLocal() as session:
        first_result = cancel_booking(session, hold_id)
        first_cancelled_at = first_result.cancelled_at

    # Retry cancellation.
    with SessionLocal() as session:
        second_result = cancel_booking(session, hold_id)

    assert second_result.status == "cancelled"
    assert second_result.cancelled_at == first_cancelled_at
    assert second_result.refund_eligible is True


def test_cancelled_slot_can_be_booked_by_another_member():
    with SessionLocal() as setup_session:
        member_one = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Member One",
        )

        member_two = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Member Two",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member_one, member_two, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_one_id = member_one.id
        member_two_id = member_two.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=48)

    # First member creates and confirms the booking.
    with SessionLocal() as session:
        first_hold = create_hold(
            session, member_one_id, court_id, start_time
        )
        first_hold_id = first_hold.id

    with SessionLocal() as session:
        confirm_hold(session, first_hold_id)

    # First member cancels the booking.
    with SessionLocal() as session:
        cancelled = cancel_booking(session, first_hold_id)
        assert cancelled.status == "cancelled"

    # Second member books the same slot.
    with SessionLocal() as session:
        second_hold = create_hold(
            session, member_two_id, court_id, start_time
        )

        assert second_hold.status == "held"
        assert second_hold.member_id == member_two_id
        assert second_hold.court_id == court_id


def test_cancel_nonexistent_booking():
    with SessionLocal() as session:
        try:
            cancel_booking(session, 999999)
            assert False, "Expected BookingNotFoundError"
        except BookingNotFoundError:
            pass


def test_cannot_cancel_unconfirmed_hold():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=48)

    # Create hold but do not confirm it.
    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    # Cancellation must be rejected.
    with SessionLocal() as session:
        try:
            cancel_booking(session, hold_id)
            assert False, "Expected BookingCancellationError"
        except BookingCancellationError:
            pass

    # Verify the hold remains active.
    with SessionLocal() as session:
        hold = session.get(CourtReservation, hold_id)
        assert hold.status == "held"
        assert hold.cancelled_at is None


def test_concurrent_cancellation_is_idempotent():
    with SessionLocal() as setup_session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Test Member",
        )

        venue = Venue(
            name="Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        setup_session.add_all([member, venue])
        setup_session.flush()

        court = Court(
            venue_id=venue.id,
            name="Test Court",
            sport_type="Badminton",
        )

        setup_session.add(court)
        setup_session.commit()

        member_id = member.id
        court_id = court.id

    start_time = datetime.now(timezone.utc) + timedelta(hours=48)

    with SessionLocal() as session:
        hold = create_hold(session, member_id, court_id, start_time)
        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    barrier = Barrier(2)

    def cancel_from_separate_session():
        with SessionLocal() as session:
            barrier.wait(timeout=10)
            result = cancel_booking(session, hold_id)
            return result.id, result.status, result.cancelled_at

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(cancel_from_separate_session)
        future_two = executor.submit(cancel_from_separate_session)

        result_one = future_one.result(timeout=15)
        result_two = future_two.result(timeout=15)

    assert result_one == result_two
    assert result_one[0] == hold_id
    assert result_one[1] == "cancelled"
    assert result_one[2] is not None


def test_court_availability_returns_open_slots():
    tomorrow = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    with SessionLocal() as session:
        member = Member(
            email="availability@example.com",
            full_name="Availability Test Member",
        )

        venue = Venue(
            name="Availability Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="06:00",
            closing_time="10:00",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Availability Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        court_id = court.id

    with SessionLocal() as session:
        slots = get_court_availability(
            session,
            court_id,
            tomorrow,
        )

    assert len(slots) == 4
    assert all(slot["available"] for slot in slots)

    assert slots[0]["starts_at"].hour == 6
    assert slots[-1]["ends_at"].hour == 10


def test_confirmed_booking_makes_slot_unavailable():
    tomorrow = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    with SessionLocal() as session:
        member = Member(
            email="availability_confirmed@example.com",
            full_name="Availability Test Member",
        )

        venue = Venue(
            name="Availability Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="06:00",
            closing_time="10:00",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Availability Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    booking_start = datetime.combine(
        tomorrow,
        time(7, 0),
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )

    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            booking_start,
        )
        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    with SessionLocal() as session:
        slots = get_court_availability(
            session,
            court_id,
            tomorrow,
        )

    assert len(slots) == 4
    assert slots[0]["available"] is True
    assert slots[1]["available"] is False
    assert slots[2]["available"] is True
    assert slots[3]["available"] is True


def test_active_hold_makes_slot_unavailable():
    tomorrow = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    with SessionLocal() as session:
        member = Member(
            email="availability_hold@example.com",
            full_name="Availability Test Member",
        )

        venue = Venue(
            name="Availability Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="06:00",
            closing_time="10:00",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Availability Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    hold_start = datetime.combine(
        tomorrow,
        time(7, 0),
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )

    with SessionLocal() as session:
        create_hold(
            session,
            member_id,
            court_id,
            hold_start,
        )

    with SessionLocal() as session:
        slots = get_court_availability(
            session,
            court_id,
            tomorrow,
        )

    assert len(slots) == 4
    assert slots[0]["available"] is True
    assert slots[1]["available"] is False
    assert slots[2]["available"] is True
    assert slots[3]["available"] is True


def test_expired_hold_does_not_make_slot_unavailable():
    tomorrow = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    with SessionLocal() as session:
        member = Member(
            email="availability_expired@example.com",
            full_name="Availability Test Member",
        )

        venue = Venue(
            name="Availability Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="06:00",
            closing_time="10:00",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Availability Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    hold_start = datetime.combine(
        tomorrow,
        time(7, 0),
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )

    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            hold_start,
        )
        hold_id = hold.id

    # Simulate an expired hold.
    with SessionLocal() as session:
        with session.begin():
            reservation = session.get(
                CourtReservation,
                hold_id,
            )
            reservation.expires_at = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            )

    with SessionLocal() as session:
        slots = get_court_availability(
            session,
            court_id,
            tomorrow,
        )

    assert len(slots) == 4
    assert all(slot["available"] for slot in slots)


def test_cancelled_reservation_does_not_block_slot():
    tomorrow = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    with SessionLocal() as session:
        member = Member(
            email="availability_cancelled@example.com",
            full_name="Availability Test Member",
        )

        venue = Venue(
            name="Availability Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="06:00",
            closing_time="10:00",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Availability Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    booking_start = datetime.combine(
        tomorrow,
        time(7, 0),
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )

    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            booking_start,
        )
        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    with SessionLocal() as session:
        cancel_booking(session, hold_id)

    with SessionLocal() as session:
        slots = get_court_availability(
            session,
            court_id,
            tomorrow,
        )

    assert len(slots) == 4
    assert all(slot["available"] for slot in slots)


def test_valid_operating_hours():
    validate_operating_hours("06:00", "22:00")


def test_invalid_operating_hours_format():
    with pytest.raises(ValueError):
        validate_operating_hours("25:90", "22:00")


def test_opening_time_must_be_before_closing_time():
    with pytest.raises(ValueError):
        validate_operating_hours("22:00", "06:00")

def test_venue_model_rejects_invalid_operating_hours():
    with pytest.raises(ValueError):
        Venue(
            name="Invalid Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="25:90",
            closing_time="22:00",
        )


def test_database_rejects_invalid_operating_hours():
    with SessionLocal() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                session.execute(
                    text("""
                        INSERT INTO venues
                        (name, timezone, address, opening_time, closing_time)
                        VALUES (
                            'Invalid DB Venue',
                            'Asia/Kolkata',
                            'Test Address',
                            '25:90',
                            '22:00'
                        )
                    """)
                )

def test_off_peak_booking_uses_base_price(db_session, test_member, test_court):
    venue = test_court.venue
    venue.base_price = 500.00
    venue.peak_price = 750.00

    local_start = datetime.now(
        ZoneInfo(venue.timezone)
    ).replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0,
    ) + timedelta(days=1)

    reservation = create_hold(
        session=db_session,
        member_id=test_member.id,
        court_id=test_court.id,
        starts_at=local_start,
    )

    assert reservation.price == Decimal("500.00")


def test_peak_booking_uses_peak_price(db_session, test_member, test_court):
    venue = test_court.venue
    venue.base_price = 500.00
    venue.peak_price = 750.00

    local_start = datetime.now(
        ZoneInfo(venue.timezone)
    ).replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
    ) + timedelta(days=1)

    reservation = create_hold(
        session=db_session,
        member_id=test_member.id,
        court_id=test_court.id,
        starts_at=local_start,
    )

    assert reservation.price == Decimal("750.00")

def create_pricing_test_data():
    with SessionLocal() as session:
        member = Member(
            email=f"pricing_{uuid4().hex[:8]}@example.com",
            full_name="Pricing Test Member",
        )

        venue = Venue(
            name="Pricing Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            base_price=500.00,
            peak_price=750.00,
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Pricing Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        return member.id, court.id


def test_off_peak_booking_uses_base_price():
    member_id, court_id = create_pricing_test_data()

    local_start = (
        datetime.now(ZoneInfo("Asia/Kolkata"))
        .replace(hour=10, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    )

    with SessionLocal() as session:
        reservation = create_hold(
            session=session,
            member_id=member_id,
            court_id=court_id,
            starts_at=local_start,
        )

        assert reservation.price == Decimal("500.00")


def test_peak_booking_uses_peak_price():
    member_id, court_id = create_pricing_test_data()

    local_start = (
        datetime.now(ZoneInfo("Asia/Kolkata"))
        .replace(hour=19, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    )

    with SessionLocal() as session:
        reservation = create_hold(
            session=session,
            member_id=member_id,
            court_id=court_id,
            starts_at=local_start,
        )

        assert reservation.price == Decimal("750.00")

def test_price_remains_unchanged_after_confirmation():
    member_id, court_id = create_pricing_test_data()

    local_start = (
        datetime.now(ZoneInfo("Asia/Kolkata"))
        .replace(hour=19, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    )

    with SessionLocal() as session:
        reservation = create_hold(
            session=session,
            member_id=member_id,
            court_id=court_id,
            starts_at=local_start,
        )

        reservation_id = reservation.id

        assert reservation.price == Decimal("750.00")

    # Change venue pricing after the hold has been created.
    with SessionLocal() as session:
        venue = session.scalar(
            select(Venue)
            .join(Court, Court.venue_id == Venue.id)
            .where(Court.id == court_id)
        )
        venue.peak_price = 900.00
        session.commit()

    with SessionLocal() as session:
        confirmed = confirm_hold(session, reservation_id)

        assert confirmed.status == "confirmed"
        assert confirmed.price == Decimal("750.00")