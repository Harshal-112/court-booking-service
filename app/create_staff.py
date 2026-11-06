
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.services.staff_service import create_staff_member


email_validator = TypeAdapter(EmailStr)


def main():
    print("\n=== Staff Account Provisioning ===\n")

    email = input("Staff email: ").strip()
    full_name = input("Full name: ").strip()

    if not email:
        print("\nError: Email is required.")
        return

    try:
        email = str(email_validator.validate_python(email)).lower()
    except ValidationError:
        print("\nError: Enter a valid email address.")
        return

    if not full_name:
        print("\nError: Full name is required.")
        return

    password = getpass("Password: ")
    confirm_password = getpass("Confirm password: ")

    if password != confirm_password:
        print("\nError: Passwords do not match.")
        return

    db = None

    try:
        db = SessionLocal()

        staff = create_staff_member(
            db=db,
            email=email,
            full_name=full_name,
            password=password,
        )

        print("\nStaff account created successfully.")
        print(f"Member ID: {staff.id}")
        print(f"Email: {staff.email}")
        print(f"Role: {staff.role}")

    except ValueError as exc:
        print(f"\nError: {exc}")

    except SQLAlchemyError:
        if db is not None:
            db.rollback()

        print("\nError: Database operation failed.")

    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    main()
