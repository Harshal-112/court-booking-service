from decimal import Decimal
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    EmailStr,
    field_validator,
)

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters.")

        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str

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


class CourtSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    name: str
    sport_type: str


class VenueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str


class DashboardStats(BaseModel):
    upcoming_bookings: int
    total_bookings: int
    refunds: int
    wallet_balance: float


class BookingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    court_id: int
    court_name: str
    venue_name: str
    sport_type: str
    starts_at: datetime
    ends_at: datetime
    price: Decimal
    status: str
    refund_eligible: bool
    cancelled_at: datetime | None = None


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