from uuid import UUID
from fastapi import Depends, APIRouter, Response as FastResponse
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.credit.infrastructure.service import CreditService, get_credit_service
from src.modules.users.infrastructure.auth import CurrentUser, get_current_user_id
from src.modules.users.infrastructure.permissions import require_admin, require_client, require_workshop_owner
from src.modules.credit.application.create import (
    MyCreditLineDTO,
    CreditLineDetailDTO,
    AdminCreditLineDTO,
    AdminCreditLineListDTO,
    AdminCreditUpdateRequest,
    CheckoutEligibilityRequest,
    CheckoutEligibilityDTO,
    LimitReviewResponse,
    AdminLimitReviewListDTO,
    AdminReviewRequest,
    LateFeeDTO,
    LateFeeListDTO,
    PayLateFeeRequest,
)
from src.utils.handle_service_result import handle_service_result


class CreditRouter(BaseRouter):
    __prefix__ = "/credit"
    __tag__ = "Credit"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.get("/my-line", response_model=CoreResponse[MyCreditLineDTO])
        async def get_my_line(
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_my_line(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get("/my-line/{line_type}", response_model=CoreResponse[CreditLineDetailDTO])
        async def get_line_detail(
            line_type: str,
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_line_detail(user_id, line_type)
            handle_service_result(result, response)
            return result

        @self._router.post("/checkout-eligibility", response_model=CoreResponse[CheckoutEligibilityDTO])
        async def check_eligibility(
            body: CheckoutEligibilityRequest,
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.check_checkout_eligibility(
                user_id, body.total_financed_parts, body.total_financed_service
            )
            handle_service_result(result, response)
            return result

        # Admin endpoints
        @self._router.get("/admin/lines", response_model=CoreResponse[AdminCreditLineListDTO])
        async def admin_list_lines(
            response: FastResponse,
            _: CurrentUser = Depends(require_admin),
            service: CreditService = Depends(get_credit_service),
        ):
            result = await service.admin_list_lines()
            handle_service_result(result, response)
            return result

        @self._router.get("/admin/lines/{user_id}", response_model=CoreResponse[AdminCreditLineDTO])
        async def admin_get_line(
            user_id: UUID,
            response: FastResponse,
            _: CurrentUser = Depends(require_admin),
            service: CreditService = Depends(get_credit_service),
        ):
            result = await service.admin_get_line(user_id)
            handle_service_result(result, response)
            return result

        @self._router.put("/admin/lines/{user_id}", response_model=CoreResponse[MyCreditLineDTO])
        async def admin_update_line(
            user_id: UUID,
            body: AdminCreditUpdateRequest,
            response: FastResponse,
            _: CurrentUser = Depends(require_admin),
            service: CreditService = Depends(get_credit_service),
        ):
            result = await service.admin_update_line(
                user_id, body.parts_credit_limit, body.service_credit_limit
            )
            handle_service_result(result, response)
            return result

        # Limit review endpoints
        @self._router.post("/request-limit-review", response_model=CoreResponse)
        async def request_limit_review(
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.request_limit_review(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get("/my-limit-requests", response_model=CoreResponse[list[LimitReviewResponse]])
        async def get_my_limit_requests(
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_my_limit_requests(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/admin/limit-requests",
            response_model=CoreResponse[AdminLimitReviewListDTO],
        )
        async def admin_list_limit_requests(
            response: FastResponse,
            _: CurrentUser = Depends(require_admin),
            service: CreditService = Depends(get_credit_service),
        ):
            result = await service.admin_list_limit_requests()
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/admin/limit-requests/{request_id}",
            response_model=CoreResponse,
        )
        async def admin_review_limit_request(
            request_id: UUID,
            body: AdminReviewRequest,
            response: FastResponse,
            _: CurrentUser = Depends(require_admin),
            service: CreditService = Depends(get_credit_service),
            admin_user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.admin_review_limit_request(
                request_id, admin_user_id, body
            )
            handle_service_result(result, response)
            return result

        # Late fee endpoints
        @self._router.get("/payment-destinations")
        async def list_payment_destinations(
            _: CurrentUser = Depends(get_current_user_id),
        ):
            """List active admin payment methods for mora/commission payments."""
            from src.config.models import AdminPaymentMethod as APModel
            from src.config.database import get_session
            from sqlalchemy import select

            async with get_session() as session:
                stmt = select(APModel).where(APModel.is_active == 1).order_by(APModel.created_at.desc())
                r = await session.execute(stmt)
                methods = r.scalars().all()

            from fastapi import Response as FastResponse
            import json
            payload = [
                    {
                        "id": str(m.id),
                        "label": m.label,
                        "method_type": m.method_type,
                        "bank_name": m.bank_name,
                        "account_number": m.account_number,
                        "holder_name": m.holder_name,
                        "holder_ci": m.holder_ci,
                        "phone": m.phone,
                        "email": m.email,
                    }
                    for m in methods
                ]
            return FastResponse(
                content=json.dumps({"success": True, "status_code": 200, "content": payload}),
                media_type="application/json",
                status_code=200,
            )

        @self._router.get("/my-late-fees", response_model=CoreResponse[LateFeeListDTO])
        async def list_my_late_fees(
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list_my_late_fees(user_id)
            handle_service_result(result, response)
            return result

        @self._router.post("/late-fees/{late_fee_id}/pay", response_model=CoreResponse[LateFeeDTO])
        async def pay_late_fee(
            late_fee_id: UUID,
            body: PayLateFeeRequest,
            response: FastResponse,
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.pay_late_fee(late_fee_id, body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post("/late-fees/{late_fee_id}/mark-paid", response_model=CoreResponse[LateFeeDTO])
        async def mark_late_fee_paid(
            late_fee_id: UUID,
            response: FastResponse,
            _: CurrentUser = Depends(require_workshop_owner),
            service: CreditService = Depends(get_credit_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.mark_late_fee_paid(late_fee_id, user_id)
            handle_service_result(result, response)
            return result
