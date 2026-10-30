from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HoldCreateRequest(BaseModel):
    member_id: int = Field(gt=0)
    court_id: int = Field(gt=0)
    starts_at: datetime

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

