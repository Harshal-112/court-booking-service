
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Member
from app.security import hash_password


email_validator = TypeAdapter(EmailStr)


def create_staff_member(
    db: Session,
    email: str,
    full_name: str,
    password: str,
) -> Member:
    email = email.strip().lower()
    full_name = full_name.strip()

    try:
        email = str(email_validator.validate_python(email)).lower()
    except ValidationError:
        raise ValueError("Enter a valid email address.")

    if not 2 <= len(full_name) <= 150:
        raise ValueError(
            "Full name must contain between 2 and 150 characters."
        )

    if not 8 <= len(password) <= 128:
        raise ValueError("Password must contain 8 to 128 characters.")

    existing_member = db.scalar(
        select(Member).where(Member.email == email)
    )

    if existing_member:
        raise ValueError("An account with this email already exists.")

    staff_member = Member(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        role="staff",
    )

    try:
        db.add(staff_member)
        db.commit()
        db.refresh(staff_member)
        return staff_member

    except IntegrityError:
        db.rollback()
        raise ValueError(
            "An account with this email already exists."
        )

    except SQLAlchemyError:
        db.rollback()
        raise
