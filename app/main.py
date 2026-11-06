from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_db, get_current_member, require_staff
from app.database import SessionLocal
from app.models import Member
from app.rate_limiter import (
    record_failed_login,
    reset_account_ip_attempts,
)
from app.schema import (
    HoldCreateRequest,
    HoldResponse,
    CourtAvailabilityResponse,
    RecurringBookingRequest,
    WeeklyUtilizationResponse,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    MemberResponse,
    DashboardStats,
    BookingSummary,
)

from app.security import hash_password, verify_password, create_access_token
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
    CourtReservation,
)
from app.models import Court, CourtReservation as ReservationModel, Venue

app = FastAPI(
    title="Court Booking API",
    description="Backend for a multi-venue sports court booking system.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    http_request: Request,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()

    ip_address = (
        http_request.client.host
        if http_request.client
        else "unknown"
    )

    try:
        member = db.scalar(
            select(Member).where(Member.email == email)
        )

        password_valid = (
            member is not None
            and verify_password(
                request.password,
                member.password_hash,
            )
        )

        if not password_valid:
            allowed = record_failed_login(email, ip_address)

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Try again after 15 minutes.",
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        reset_account_ip_attempts(email, ip_address)

        token = create_access_token(member.id, member.role)

        return {
            "access_token": token,
            "token_type": "bearer",
        }

    except RedisError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login service temporarily unavailable.",
        )

@app.get("/auth/me", response_model=MemberResponse)
def get_my_profile(
    current_member: Member = Depends(get_current_member),
):
    return current_member

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


@app.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Upcoming bookings: confirmed future reservations
    upcoming_count = db.scalar(
        select(func.count(ReservationModel.id)).where(
            ReservationModel.member_id == current_member.id,
            ReservationModel.status == "confirmed",
            ReservationModel.starts_at > now,
        )
    ) or 0

    # Total bookings: all confirmed + cancelled
    total_count = db.scalar(
        select(func.count(ReservationModel.id)).where(
            ReservationModel.member_id == current_member.id,
            ReservationModel.status.in_(["confirmed", "cancelled"]),
        )
    ) or 0

    # Refunds: cancelled bookings that are refund eligible
    refunds = db.scalar(
        select(func.count(ReservationModel.id)).where(
            ReservationModel.member_id == current_member.id,
            ReservationModel.status == "cancelled",
            ReservationModel.refund_eligible == True,
        )
    ) or 0

    # Wallet balance: sum of all reservation prices (confirmed + upcoming)
    wallet = db.scalar(
        select(func.sum(ReservationModel.price)).where(
            ReservationModel.member_id == current_member.id,
            ReservationModel.status.in_(["confirmed", "held"]),
            ReservationModel.starts_at > now,
        )
    ) or 0

    return DashboardStats(
        upcoming_bookings=upcoming_count,
        total_bookings=total_count,
        refunds=refunds,
        wallet_balance=float(wallet) if wallet else 0.0,
    )


@app.get("/dashboard/bookings", response_model=list[BookingSummary])
def dashboard_bookings(
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    bookings = db.scalars(
        select(ReservationModel).where(
            ReservationModel.member_id == current_member.id,
            ReservationModel.status.in_(["confirmed", "cancelled", "held"]),
        )
        .order_by(ReservationModel.starts_at.desc())
    ).all()

    # Enrich with court and venue info
    result = []
    for booking in bookings:
        court = db.scalar(select(Court).where(Court.id == booking.court_id))
        venue = db.scalar(select(Venue).where(Venue.id == court.venue_id)) if court else None

        result.append(BookingSummary(
            id=booking.id,
            court_id=booking.court_id,
            court_name=court.name if court else "Unknown Court",
            venue_name=venue.name if venue else "Unknown Venue",
            sport_type=court.sport_type if court else "Unknown",
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            price=booking.price,
            status=booking.status,
            refund_eligible=booking.refund_eligible,
            cancelled_at=booking.cancelled_at,
        ))

    return result


@app.get("/dashboard/bookings/upcoming", response_model=list[BookingSummary])
def dashboard_upcoming_bookings(
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    bookings = db.scalars(
        select(ReservationModel).where(
            ReservationModel.member_id == current_member.id,
            ReservationModel.status == "confirmed",
            ReservationModel.starts_at > now,
        )
        .order_by(ReservationModel.starts_at.asc())
    ).all()

    # Enrich with court and venue info
    result = []
    for booking in bookings:
        court = db.scalar(select(Court).where(Court.id == booking.court_id))
        venue = db.scalar(select(Venue).where(Venue.id == court.venue_id)) if court else None

        result.append(BookingSummary(
            id=booking.id,
            court_id=booking.court_id,
            court_name=court.name if court else "Unknown Court",
            venue_name=venue.name if venue else "Unknown Venue",
            sport_type=court.sport_type if court else "Unknown",
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
            price=booking.price,
            status=booking.status,
            refund_eligible=booking.refund_eligible,
            cancelled_at=booking.cancelled_at,
        ))

    return result