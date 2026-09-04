from enum import StrEnum


class BusinessType(StrEnum):
    SALON = "SALON"
    CLINIC = "CLINIC"
    BAKERY = "BAKERY"
    FITNESS = "FITNESS"
    ACADEMY = "ACADEMY"


class BookingMode(StrEnum):
    APPOINTMENT = "APPOINTMENT"
    BATCH = "BATCH"
    CUSTOM_ORDER = "CUSTOM_ORDER"


class CustomFieldType(StrEnum):
    TEXT = "TEXT"
    DROPDOWN = "DROPDOWN"
    BOOLEAN = "BOOLEAN"
    FILE_UPLOAD = "FILE_UPLOAD"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    ADVANCE_PAID = "ADVANCE_PAID"
    FULLY_PAID = "FULLY_PAID"


class BookingStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    EXPIRED = "EXPIRED"

