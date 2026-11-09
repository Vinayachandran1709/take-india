"""Public billing response contracts. Secret credentials never appear here."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BillingSummary(BaseModel):
    effective_status: str
    trial_ends_at: datetime
    days_left: int
    current_period_end: datetime | None
    cancel_at_period_end: bool
    locked: bool
    authorization_confirmed: bool
    processing: bool


class BillingPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    razorpay_payment_id: str
    amount_paise: int
    currency: str
    status: str
    paid_at: datetime | None


class BillingDetail(BaseModel):
    summary: BillingSummary
    payments: list[BillingPaymentOut]


class SubscribeResponse(BaseModel):
    subscription_id: str
    key_id: str


class ConfirmRequest(BaseModel):
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=80)
    razorpay_subscription_id: str = Field(pattern=r"^sub_[A-Za-z0-9]+$", max_length=80)
    razorpay_signature: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class BillingActionResponse(BaseModel):
    status: str
