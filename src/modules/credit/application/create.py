from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MyCreditLineDTO(BaseModel):
    level: int
    parts_limit: float
    service_limit: float
    parts_available: float
    service_available: float
    parts_debt: float
    service_debt: float
    min_down_payment_pct: float = 0.0
    credit_points: float = 0.0
    points_to_next_level: float | None = None
    pending_points: float = 0.0


class PendingReleaseDTO(BaseModel):
    order_id: UUID
    description: str
    amount: float
    due_date: datetime
    status: str  # PENDING, PENDING_VERIFICATION, PAID


class CreditLineDetailDTO(BaseModel):
    line_type: str  # "parts" | "service"
    limit: float
    available: float
    debt: float
    pending_releases: list[PendingReleaseDTO] = []


class CreditLevelDTO(BaseModel):
    level: int
    points_required: float
    credit_multiplier: float
    min_down_payment_pct: float
    base_parts_limit: float

    model_config = ConfigDict(from_attributes=True)


class CreditHistoryDTO(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    amount: float
    parts_line_used: float
    service_line_used: float
    description: str
    reference_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminCreditLineDTO(BaseModel):
    user_id: UUID
    user_name: str
    user_email: str
    level: int
    credit_points: float
    points_to_next_level: float | None = None
    parts_limit: float
    service_limit: float
    parts_available: float
    service_available: float
    parts_debt: float
    service_debt: float
    total_spent: float = 0.0
    parts_orders_count: int = 0
    parts_orders_paid_cash: int = 0
    parts_orders_financed: int = 0
    parts_installments_on_time: int = 0
    parts_installments_late: int = 0
    service_orders_count: int = 0
    service_orders_cash: int = 0
    service_orders_financed: int = 0
    service_installments_on_time: int = 0
    service_installments_late: int = 0
    manual_adjustment: float | None = None


class AdminCreditLineListDTO(BaseModel):
    lines: list[AdminCreditLineDTO]


class AdminCreditUpdateRequest(BaseModel):
    parts_credit_limit: float | None = None
    service_credit_limit: float | None = None


class CheckoutEligibilityRequest(BaseModel):
    total_financed_parts: float
    total_financed_service: float = 0.0


class CheckoutEligibilityDTO(BaseModel):
    eligible: bool
    parts_available: float
    service_available: float
    min_down_payment_percentage: float | None = None
    message: str | None = None


class LimitReviewResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewer_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminLimitReviewDTO(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str
    user_email: str
    current_parts_limit: float
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer_name: str | None = None


class AdminLimitReviewListDTO(BaseModel):
    requests: list[AdminLimitReviewDTO]


class AdminReviewRequest(BaseModel):
    action: str = "APPROVED"  # APPROVED or REJECTED
    new_parts_limit: float | None = None


class LateFeeDTO(BaseModel):
    id: UUID
    installment_type: str
    installment_id: UUID
    amount: float
    status: str
    payment_method: str = "OTHER"
    reference_number: str | None = None
    rate: float | None = None
    rate_date: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LateFeeListDTO(BaseModel):
    late_fees: list[LateFeeDTO]


class PayLateFeeRequest(BaseModel):
    payment_method: str
    reference_number: str | None = None
    rate: float | None = None
    rate_date: str | None = None
