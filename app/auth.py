
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Member
from app.security import decode_access_token
from jwt.exceptions import InvalidTokenError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_member(
    token: str = Depends(oauth2_scheme),
) -> Member:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        member_id = int(payload.get("sub"))
    except (InvalidTokenError, TypeError, ValueError):
        raise credentials_exception

    # Use a separate database session for authentication.
    with SessionLocal() as db:
        member = db.scalar(
            select(Member).where(Member.id == member_id)
        )

        if member is None:
            raise credentials_exception

        # Return a detached Member object.
        db.expunge(member)

    return member


def require_staff(
    current_member: Member = Depends(get_current_member),
) -> Member:
    if current_member.role != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required.",
        )

    return current_member
