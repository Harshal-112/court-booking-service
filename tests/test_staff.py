import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import patch

from app.database import SessionLocal
from app.models import Member
from app.security import verify_password
from app.services.staff_service import create_staff_member
from app.create_staff import main

def test_create_staff_member_successfully():
    with SessionLocal() as db:
        staff = create_staff_member(
            db=db,
            email="  STAFF@EXAMPLE.COM  ",
            full_name="Test Staff",
            password="SecurePassword123",
        )

        assert staff.id is not None
        assert staff.email == "staff@example.com"
        assert staff.full_name == "Test Staff"
        assert staff.role == "staff"
        assert staff.password_hash != "SecurePassword123"
        assert verify_password(
            "SecurePassword123",
            staff.password_hash,
        )


def test_create_staff_member_rejects_duplicate_email():
    with SessionLocal() as db:
        create_staff_member(
            db=db,
            email="staff@example.com",
            full_name="First Staff",
            password="SecurePassword123",
        )

        with pytest.raises(
            ValueError,
            match="already exists",
        ):
            create_staff_member(
                db=db,
                email="STAFF@example.com",
                full_name="Second Staff",
                password="AnotherPassword123",
            )


@pytest.mark.parametrize(
    "full_name",
    ["", " ", "A"],
)
def test_create_staff_member_rejects_invalid_name(full_name):
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="Full name"):
            create_staff_member(
                db=db,
                email="staff@example.com",
                full_name=full_name,
                password="SecurePassword123",
            )


@pytest.mark.parametrize(
    "password",
    ["short", "x" * 129],
)
def test_create_staff_member_rejects_invalid_password(password):
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="Password"):
            create_staff_member(
                db=db,
                email="staff@example.com",
                full_name="Test Staff",
                password=password,
            )

from unittest.mock import patch

from app.create_staff import main


def test_staff_cli_rejects_empty_email(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "")

    with patch("app.create_staff.SessionLocal") as mock_session:
        main()

    assert "Email is required." in capsys.readouterr().out
    mock_session.assert_not_called()


def test_staff_cli_rejects_invalid_email(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "invalid-email")

    with patch("app.create_staff.SessionLocal") as mock_session:
        main()

    assert "valid email address" in capsys.readouterr().out
    mock_session.assert_not_called()


def test_staff_cli_rejects_password_mismatch(monkeypatch, capsys):
    inputs = iter(["staff@example.com", "Test Staff"])
    passwords = iter(["SecurePassword123", "DifferentPassword123"])

    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr("app.create_staff.getpass", lambda _: next(passwords))

    with patch("app.create_staff.SessionLocal") as mock_session:
        main()

    assert "Passwords do not match." in capsys.readouterr().out
    mock_session.assert_not_called()


def test_staff_cli_handles_database_failure(monkeypatch, capsys):
    inputs = iter(["staff@example.com", "Test Staff"])
    passwords = iter(["SecurePassword123", "SecurePassword123"])

    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr("app.create_staff.getpass", lambda _: next(passwords))

    with patch(
        "app.create_staff.SessionLocal",
        side_effect=SQLAlchemyError("Database unavailable"),
    ):
        main()

    assert "Database operation failed." in capsys.readouterr().out


def test_create_staff_member_rejects_invalid_email():
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="valid email"):
            create_staff_member(
                db=db,
                email="invalid-email",
                full_name="Test Staff",
                password="SecurePassword123",
            )


def test_create_staff_member_rejects_long_name():
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="150 characters"):
            create_staff_member(
                db=db,
                email="staff@example.com",
                full_name="A" * 151,
                password="SecurePassword123",
            )
