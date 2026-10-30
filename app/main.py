
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date

from app.database import SessionLocal
from app.schema import HoldCreateRequest, HoldResponse, CourtAvailabilityResponse
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
    )


app = FastAPI(
    title="Court Booking API",
    description="Backend for a multi-venue sports court booking system.",
    version="0.1.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    db: Session = Depends(get_db),
):
    try:
        reservation = create_hold(
            session=db,
            member_id=request.member_id,
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
    db: Session = Depends(get_db),
):
    try:
        reservation = confirm_hold(
            session=db,
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
    db: Session = Depends(get_db),
):
    try:
        reservation = cancel_booking(
            session=db,
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
