
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import select
from app.models import Member
from app.auth import get_db, get_current_member, require_staff
from app.security import hash_password, verify_password, create_access_token
from sqlalchemy.orm import Session
from datetime import date
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.schema import (
    HoldCreateRequest,
    HoldResponse,
    CourtAvailabilityResponse,
    RecurringBookingRequest,
    WeeklyUtilizationResponse,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
)
from app.services.reservation_service import (
    create_hold,
    MemberNotFoundError,
    CourtNotFoundError,
    BookingConflictError,
    InvalidBookingTimeError,
    confirm_hold,
    HoldNotFoundError,
    HoldExpiredError,
    cancel_booking,
    BookingNotFoundError,
    BookingCancellationError,
    get_court_availability,
    create_recurring_bookings,
    get_weekly_utilization,
    ReservationError,
)


app = FastAPI(
    title="Court Booking API",
    description="Backend for a multi-venue sports court booking system.",
    version="0.1.0",
)

@app.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)

def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()

    existing_member = db.scalar(
        select(Member).where(Member.email == email)
    )

    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    member = Member(
        email=email,
        full_name=request.full_name.strip(),
        password_hash=hash_password(request.password),
        role="member",
    )

    db.add(member)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        existing_member = db.scalar(
            select(Member).where(Member.email == email)
        )

        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered.",
            )

        raise

    db.refresh(member)

    token = create_access_token(member.id, member.role)

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()

    member = db.scalar(
        select(Member).where(Member.email == email)
    )

    if member is None or not verify_password(
        request.password,
        member.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(member.id, member.role)

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/holds",
    response_model=HoldResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hold_endpoint(
    request: HoldCreateRequest,
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    try:
        reservation = create_hold(
            session=db,
            member_id=current_member.id,
            court_id=request.court_id,
            starts_at=request.starts_at,
        )

        return reservation

    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except CourtNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except BookingConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except InvalidBookingTimeError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )


@app.post(
    "/holds/{hold_id}/confirm",
    response_model=HoldResponse,
)
def confirm_hold_endpoint(
    hold_id: int,
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    try:
        reservation = confirm_hold(
            session=db,
            member_id=current_member.id,
            hold_id=hold_id,
        )

        return reservation

    except HoldNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except HoldExpiredError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


@app.post(
    "/bookings/{booking_id}/cancel",
    response_model=HoldResponse,
)
def cancel_booking_endpoint(
    booking_id: int,
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    try:
        reservation = cancel_booking(
            session=db,
            member_id=current_member.id,
            booking_id=booking_id,
        )

        return reservation

    except BookingNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except BookingCancellationError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


@app.get(
    "/courts/{court_id}/availability",
    response_model=CourtAvailabilityResponse,
)
def court_availability_endpoint(
    court_id: int,
    date: date,
    db: Session = Depends(get_db),
):
    try:
        slots = get_court_availability(
            session=db,
            court_id=court_id,
            requested_date=date,
        )

        return {
            "court_id": court_id,
            "date": date,
            "slots": slots,
        }

    except CourtNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

@app.post(
    "/recurring-bookings",
    response_model=list[HoldResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_recurring_bookings_endpoint(
    request: RecurringBookingRequest,
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    try:
        reservations = create_recurring_bookings(
            session=db,
            member_id=current_member.id,
            court_id=request.court_id,
            starts_at=request.starts_at,
            weeks=request.weeks,
        )

        return reservations

    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except CourtNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except BookingConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except InvalidBookingTimeError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

@app.get(
    "/venues/{venue_id}/utilization/weekly",
    response_model=WeeklyUtilizationResponse,
)
def weekly_venue_utilization(
    venue_id: int,
    week_start: date,
    current_member: Member = Depends(require_staff),
    session: Session = Depends(get_db),
):
    try:
        return get_weekly_utilization(
            session=session,
            venue_id=venue_id,
            week_start=week_start,
        )

    except ReservationError as exc:
        if str(exc) == "Venue not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )