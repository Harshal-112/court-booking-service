
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url


DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Tests require court_booking_test."
    )

database_name = make_url(DATABASE_URL).database

if database_name != "court_booking_test":
    raise RuntimeError(
        "Safety check failed: tests can only run on court_booking_test."
    )

from app.database import engine


@pytest.fixture(autouse=True)
def clean_test_database():
    def clean():
        with engine.begin() as connection:
            connection.execute(
                text("""
                    TRUNCATE TABLE
                        court_reservations,
                        holds,
                        bookings,
                        courts,
                        venues,
                        members
                    RESTART IDENTITY CASCADE
                """)
            )

    clean()
    yield
    clean()
