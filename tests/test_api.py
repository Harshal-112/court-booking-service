
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Member, Venue, Court
from app.security import create_access_token, decode_access_token
from app.services.reservation_service import create_hold, confirm_hold
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.main import app, register
from app.schema import RegisterRequest

def auth_headers(member_id: int, role: str = "member"):
    token = create_access_token(member_id, role)
    return {"Authorization": f"Bearer {token}"}


def test_create_hold_api():
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
            password_hash="test-hash",
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

    client = TestClient(app)

    response = client.post(
        "/holds",
        headers=auth_headers(member_id),
        json={
            "court_id": court_id,
            "starts_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert "member_id" not in data
    assert data["court_id"] == court_id
    assert data["status"] == "held"
    assert data["expires_at"] is not None


def test_create_hold_with_invalid_member():
    client = TestClient(app)

    response = client.post(
        "/holds",
        json={
            "court_id": 999999,
            "starts_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    )

    assert response.status_code == 401


def test_create_hold_with_invalid_court():
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
            password_hash="test-hash",
        )

        session.add(member)
        session.commit()

        member_id = member.id

    client = TestClient(app)

    response = client.post(
        "/holds",
        headers=auth_headers(member_id),
        json={
            "court_id": 999999,
            "starts_at": (
                datetime.now(timezone.utc) + timedelta(hours=2)
            ).isoformat(),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Court not found."

def test_protected_endpoint_rejects_invalid_token():
    client = TestClient(app)

    response = client.post(
        "/holds/1/confirm",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token."
    )

def test_confirm_hold_api():
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
            password_hash="test-hash",
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

    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=2),
        )

        hold_id = hold.id

    client = TestClient(app)

    response = client.post(
        f"/holds/{hold_id}/confirm",
        headers=auth_headers(member_id),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == hold_id
    assert data["status"] == "confirmed"
    assert data["expires_at"] is None


def test_cancel_booking_api():
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
            password_hash="test-hash",
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

    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=48),
        )

        hold_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, hold_id, member_id)

    client = TestClient(app)

    response = client.post(
        f"/bookings/{hold_id}/cancel",
        headers=auth_headers(member_id),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == hold_id
    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None
    assert data["refund_eligible"] is True


def test_cancel_unconfirmed_hold_api():
    with SessionLocal() as session:
        member = Member(
            email=f"api_{uuid4().hex[:8]}@example.com",
            full_name="API Test Member",
            password_hash="test-hash",
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

    with SessionLocal() as session:
        hold = create_hold(
            session,
            member_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=48),
        )

        hold_id = hold.id

    client = TestClient(app)

    response = client.post(
        f"/bookings/{hold_id}/cancel",
        headers=auth_headers(member_id),
    )

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


def test_create_recurring_bookings_api():
    with SessionLocal() as session:
        member = Member(
            email=f"recurring_api_{uuid4().hex[:8]}@example.com",
            full_name="Recurring API Test Member",
            password_hash="test-hash",
        )

        venue = Venue(
            name="Recurring API Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Recurring API Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    client = TestClient(app)

    starts_at = (
        datetime.now(timezone.utc) + timedelta(days=2)
    ).replace(minute=0, second=0, microsecond=0)

    response = client.post(
        "/recurring-bookings",
        headers=auth_headers(member_id),
        json={
            "court_id": court_id,
            "starts_at": starts_at.isoformat(),
            "weeks": 3,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert len(data) == 3
    assert all(item["status"] == "confirmed" for item in data)
    assert all(item["expires_at"] is None for item in data)


def test_recurring_bookings_api_rejects_member_limit():
    with SessionLocal() as session:
        member = Member(
            email=f"recurring_limit_{uuid4().hex[:8]}@example.com",
            full_name="Recurring Limit Test Member",
            password_hash="test-hash",
        )

        venue = Venue(
            name="Recurring Limit Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([member, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Recurring Limit Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        member_id = member.id
        court_id = court.id

    starts_at = (
        datetime.now(timezone.utc) + timedelta(days=2)
    ).replace(minute=0, second=0, microsecond=0)

    client = TestClient(app)

    response = client.post(
        "/recurring-bookings",
        headers=auth_headers(member_id),
        json={
            "court_id": court_id,
            "starts_at": starts_at.isoformat(),
            "weeks": 4,
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == (
        "Recurring bookings exceed the maximum of 3 active future reservations."
    )

def test_member_cannot_access_staff_utilization_api():
    with SessionLocal() as session:
        member = Member(
            email=f"member_{uuid4().hex[:8]}@example.com",
            full_name="Regular Member",
            password_hash="test-hash",
            role="member",
        )

        session.add(member)
        session.commit()

        member_id = member.id

    client = TestClient(app)

    response = client.get(
        "/venues/1/utilization/weekly",
        headers=auth_headers(member_id, role="member"),
        params={"week_start": datetime.now(timezone.utc).date().isoformat()},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Staff access required."

def test_member_cannot_cancel_another_members_booking():
    with SessionLocal() as session:
        owner = Member(
            email=f"owner_{uuid4().hex[:8]}@example.com",
            full_name="Booking Owner",
            password_hash="test-hash",
            role="member",
        )

        attacker = Member(
            email=f"attacker_{uuid4().hex[:8]}@example.com",
            full_name="Another Member",
            password_hash="test-hash",
            role="member",
        )

        venue = Venue(
            name="Ownership Test Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([owner, attacker, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Ownership Test Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        owner_id = owner.id
        attacker_id = attacker.id
        court_id = court.id

    with SessionLocal() as session:
        hold = create_hold(
            session,
            owner_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=48),
        )
        booking_id = hold.id

    with SessionLocal() as session:
        confirm_hold(session, booking_id, owner_id)

    client = TestClient(app)

    response = client.post(
        f"/bookings/{booking_id}/cancel",
        headers=auth_headers(attacker_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found."

def test_member_cannot_confirm_another_members_hold():
    with SessionLocal() as session:
        owner = Member(
            email=f"owner_{uuid4().hex[:8]}@example.com",
            full_name="Hold Owner",
            password_hash="test-hash",
            role="member",
        )

        attacker = Member(
            email=f"attacker_{uuid4().hex[:8]}@example.com",
            full_name="Another Member",
            password_hash="test-hash",
            role="member",
        )

        venue = Venue(
            name="Hold Ownership Venue",
            timezone="Asia/Kolkata",
            address="Test Address",
        )

        session.add_all([owner, attacker, venue])
        session.flush()

        court = Court(
            venue_id=venue.id,
            name="Hold Ownership Court",
            sport_type="Badminton",
        )

        session.add(court)
        session.commit()

        owner_id = owner.id
        attacker_id = attacker.id
        court_id = court.id

    with SessionLocal() as session:
        hold = create_hold(
            session,
            owner_id,
            court_id,
            datetime.now(timezone.utc) + timedelta(hours=2),
        )
        hold_id = hold.id

    client = TestClient(app)

    response = client.post(
        f"/holds/{hold_id}/confirm",
        headers=auth_headers(attacker_id),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Hold not found."

def test_register_api_success():
    client = TestClient(app)
    email = f"register_{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "New Test Member",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    payload = decode_access_token(data["access_token"])
    assert payload["role"] == "member"


def test_register_api_rejects_duplicate_email():
    client = TestClient(app)
    email = f"duplicate_{uuid4().hex[:8]}@example.com"

    payload = {
        "email": email,
        "full_name": "Duplicate Test Member",
        "password": "StrongPass123",
    }

    first_response = client.post("/auth/register", json=payload)
    second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Email is already registered."


def test_register_api_cannot_assign_staff_role():
    client = TestClient(app)
    email = f"role_{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Role Test Member",
            "password": "StrongPass123",
            "role": "staff",
        },
    )

    assert response.status_code == 201

    payload = decode_access_token(response.json()["access_token"])
    assert payload["role"] == "member"


def test_login_api_success():
    client = TestClient(app)
    email = f"login_{uuid4().hex[:8]}@example.com"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Login Test Member",
            "password": "StrongPass123",
        },
    )

    assert register_response.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    payload = decode_access_token(data["access_token"])
    assert payload["role"] == "member"


def test_login_api_rejects_invalid_password():
    client = TestClient(app)
    email = f"invalid_{uuid4().hex[:8]}@example.com"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Invalid Login Member",
            "password": "StrongPass123",
        },
    )

    assert register_response.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."

def test_register_handles_database_duplicate_conflict():
    existing_member = Member(
        id=999,
        email="race@example.com",
        full_name="Existing Member",
        password_hash="test-hash",
    )

    class FakeDB:
        def __init__(self):
            self.scalar_calls = 0
            self.rolled_back = False

        def scalar(self, query):
            self.scalar_calls += 1

            if self.scalar_calls == 1:
                return None

            return existing_member

        def add(self, member):
            pass

        def commit(self):
            raise IntegrityError(
                "INSERT",
                {},
                Exception("Duplicate email"),
            )

        def rollback(self):
            self.rolled_back = True

    fake_db = FakeDB()

    request = RegisterRequest(
        email="race@example.com",
        full_name="New Member",
        password="StrongPass123",
    )

    try:
        register(request, fake_db)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "Email is already registered."

    assert fake_db.rolled_back is True
    assert fake_db.scalar_calls == 2