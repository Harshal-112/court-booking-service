from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HoldCreateRequest(BaseModel):
    court_id: int = Field(gt=0)
    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone")
        return value

class RecurringBookingRequest(BaseModel):
    court_id: int = Field(gt=0)
    starts_at: datetime
    weeks: int = Field(ge=1, le=12)

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone")
        return value

class HoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    court_id: int
    starts_at: datetime
    ends_at: datetime
    price: Decimal
    expires_at: datetime | None
    cancelled_at: datetime | None = None
    refund_eligible: bool = False
    status: str


class AvailabilitySlot(BaseModel):
    starts_at: datetime
    ends_at: datetime
    available: bool


class CourtAvailabilityResponse(BaseModel):
    court_id: int
    date: date
    slots: list[AvailabilitySlot]

class CourtUtilization(BaseModel):
    court_id: int
    court_name: str
    total_operating_hours: Decimal
    confirmed_booking_hours: Decimal
    active_hold_hours: Decimal
    utilization_percentage: Decimal
    booking_count: int


class WeeklyUtilizationResponse(BaseModel):
    venue_id: int
    venue_name: str
    week_start: date
    week_end: date
    courts: list[CourtUtilization]