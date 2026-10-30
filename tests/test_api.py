
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Member, Venue, Court

from app.services.reservation_service import create_hold
from app.services.reservation_service import create_hold, confirm_hold

def test_create_hold_api():
    # Arrange: Create test data.
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
        )

        venue = Venue(
            name="API Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="API Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    # Act: Send an actual HTTP request through TestClient.
    client = TestClient(app)

    response = client.post(
        "/holds",
        json={
            "member_id": member_id,
            "court_id": court_id,
            "starts_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    )

    # Assert: Verify HTTP response.
    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert "member_id" not in data  # Member ID is not exposed in response.
    assert data["court_id"] == court_id
    assert data["status"] == "held"
    assert data["expires_at"] is not None


def test_create_hold_with_invalid_member():
    client = TestClient(app)

    response = client.post(
        "/holds",
        json={
            "member_id": 999999,
            "court_id": 999999,
            "starts_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found."


def test_create_hold_with_invalid_court():
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
        )

        session.add(member)
        session.commit()
        member_id = member.id

    client = TestClient(app)

    response = client.post(
        "/holds",
        json={
            "member_id": member_id,
            "court_id": 999999,
            "starts_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Court not found."


def test_confirm_hold_api():
    # Arrange: Create a valid member, venue and court.
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
        )

        venue = Venue(
            name="API Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="API Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    # Create a hold.
    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=2),
        )
        hold_id = hold.id

    # Act: Confirm through HTTP API.
    client = TestClient(app)

    response = client.post(f"/holds/{hold_id}/confirm")

    # Assert.
    assert response.status_code == 200

    data = response.json()

    assert data["id"] == hold_id
    assert data["status"] == "confirmed"
    assert data["expires_at"] is None


def test_cancel_booking_api():
    # Arrange: Create member, venue and court.
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
        )

        venue = Venue(
            name="API Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="API Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    # Create and confirm a hold.
    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=48),
        )
        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id)

    # Act: Cancel through the API.
    client = TestClient(app)
    response = client.post(f"/bookings/{hold_id}/cancel")

    # Assert.
    assert response.status_code == 200

    data = response.json()

    assert data["id"] == hold_id
    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None
    assert data["refund_eligible"] is True


def test_cancel_unconfirmed_hold_api():
    # Arrange: Create member, venue and court.
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
        )

        venue = Venue(
            name="API Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="API Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    # Create a hold but do not confirm it.
    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=48),
        )
        hold_id = hold.id

    # Act: Try cancelling the unconfirmed hold.
    client = TestClient(app)
    response = client.post(f"/bookings/{hold_id}/cancel")

    # Assert.
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Only confirmed bookings can be cancelled."
    )


def test_court_availability_api():
    requested_date = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    with SessionLocal() as session:
        venue = Venue(
            name="API Availability Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
            opening_time="06:00",
            closing_time="10:00",
        )

        session.add(venue)
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="API Availability Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        court_id = court.id

    client = TestClient(app)

    response = client.get(
        f"/courts/{court_id}/availability",
        params={"date": requested_date.isoformat()},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["court_id"] == court_id
    assert data["date"] == requested_date.isoformat()
    assert len(data["slots"]) == 4
    assert all(slot["available"] for slot in data["slots"])


def test_court_availability_api_invalid_court():
    requested_date = (
        datetime.now(timezone.utc) + timedelta(days=1)
    ).date()

    client = TestClient(app)

    response = client.get(
        "/courts/999999/availability",
        params={"date": requested_date.isoformat()},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Court not found."
