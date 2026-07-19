from uuid import UUID
from fastapi import Depends, APIRouter, Response, Form, File, UploadFile
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.workshops.infrastructure.service import (
    WorkshopService,
    get_workshop_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id, CurrentUser
from src.modules.users.infrastructure.permissions import (
    require_admin,
    require_workshop_owner,
)
from src.utils.handle_service_result import handle_service_result
from src.utils.file_upload import save_upload_file
from src.modules.workshops.application.create import (
    CreateWorkshopRequest,
    UpdateWorkshopRequest,
    WorkshopDTO,
    WorkshopListDTO,
    VerificationRequestListDTO,
    CreateBankAccountRequest,
    UpdateBankAccountRequest,
    BankAccountDTO,
    BankAccountListDTO,
    CreateMobilePaymentRequest,
    UpdateMobilePaymentRequest,
    MobilePaymentDTO,
    MobilePaymentListDTO,
    WorkshopBankListDTO,
    CreatePaymentMethodRequest,
    UpdatePaymentMethodRequest,
    PaymentMethodDTO,
    PaymentMethodListDTO,
    RateWorkshopRequest,
)


class WorkshopRouter(BaseRouter):
    __prefix__ = "/workshops"
    __tag__ = "Workshops"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.post(
            "", response_model=CoreResponse[WorkshopDTO], status_code=201
        )
        async def create(
            response: Response,
            name: str = Form(...),
            rif: str = Form(...),
            address: str = Form(...),
            latitude: float | None = Form(None),
            longitude: float | None = Form(None),
            verification_document: UploadFile | None = File(None),
            photo: UploadFile | None = File(None),
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            body = CreateWorkshopRequest(
                name=name,
                rif=rif,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
            doc_url = None
            if verification_document:
                doc_url = await save_upload_file(
                    verification_document, "verification_documents"
                )
            photo_url = None
            if photo:
                photo_url = await save_upload_file(photo, "workshop_photos")
            result = await service.create(body, user_id, doc_url, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.get("", response_model=CoreResponse[WorkshopListDTO])
        async def list_workshops(
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            query: str | None = None,
            certified_only: bool = False,
            owned: bool = False,
            offset: int = 0,
            limit: int = 100,
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list(
                query=query,
                certified_only=certified_only,
                owner_id=user_id if owned else None,
                offset=offset,
                limit=limit,
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/verifications/pending",
            response_model=CoreResponse[VerificationRequestListDTO],
        )
        async def list_pending_verifications(
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            _: CurrentUser = Depends(require_admin),
        ):
            result = await service.list_pending_verifications()
            handle_service_result(result, response)
            return result

        @self._router.get("/banks", response_model=CoreResponse[WorkshopBankListDTO])
        async def list_banks():
            return WorkshopService.get_banks()

        # -- Workshop Owner Commissions (must be before /{id} to avoid UUID match) --

        @self._router.get("/my-commissions")
        async def my_commissions(
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            from src.config.database import get_session
            from src.config.models import Workshop as WorkshopModel, WorkshopCommission as WCModel
            from sqlalchemy import select
            from datetime import datetime, timezone
            import json
            from fastapi import Response as FastResponse

            async with get_session() as session:
                ws_stmt = select(WorkshopModel.id, WorkshopModel.name).where(
                    WorkshopModel.owner_id == current_user.id
                )
                ws_r = await session.execute(ws_stmt)
                workshops = ws_r.all()
                ws_ids = [w.id for w in workshops]
                ws_names = {w.id: w.name for w in workshops}

                if not ws_ids:
                    return FastResponse(
                        content=json.dumps({"success": True, "status_code": 200, "content": {"commissions": [], "total_pending": 0, "total_paid": 0}}),
                        media_type="application/json",
                        status_code=200,
                    )

                comm_stmt = (
                    select(WCModel)
                    .where(WCModel.workshop_id.in_(ws_ids))
                    .order_by(WCModel.created_at.desc())
                )
                r = await session.execute(comm_stmt)
                commissions = r.scalars().all()

                total_pending = sum(c.commission_amount for c in commissions if c.status in ("PENDING", "PENDING_VERIFICATION"))
                total_paid = sum(c.commission_amount for c in commissions if c.status == "PAID")

                items = [
                    {
                        "id": str(c.id),
                        "workshop_id": str(c.workshop_id),
                        "workshop_name": ws_names.get(c.workshop_id, ""),
                        "order_id": str(c.order_id) if c.order_id else None,
                        "service_order_id": str(c.service_order_id) if c.service_order_id else None,
                        "financed_amount": c.financed_amount,
                        "commission_rate": c.commission_rate,
                        "commission_amount": c.commission_amount,
                        "period_month": c.period_month,
                        "period_year": c.period_year,
                        "status": c.status,
                        "created_at": c.created_at.isoformat() if c.created_at else "",
                        "paid_at": c.paid_at.isoformat() if c.paid_at else None,
                    }
                    for c in commissions
                ]

            return FastResponse(
                content=json.dumps({"success": True, "status_code": 200, "content": {
                    "commissions": items,
                    "total_pending": round(total_pending, 2),
                    "total_paid": round(total_paid, 2),
                }}),
                media_type="application/json",
                status_code=200,
            )

        @self._router.patch("/my-commissions/{commission_id}/register-payment", response_model=CoreResponse)
        async def register_my_commission_payment(
            commission_id: UUID,
            body: dict,
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            from src.config.database import get_session
            from src.config.models import WorkshopCommission as WCModel, Workshop as WorkshopModel
            from sqlalchemy import select

            async with get_session() as session:
                commission = await session.get(WCModel, commission_id)
                if not commission:
                    raise HTTPException(status_code=404, detail="Comisión no encontrada")
                # Verify ownership
                ws = await session.get(WorkshopModel, commission.workshop_id)
                if not ws or ws.owner_id != current_user.id:
                    raise HTTPException(status_code=403, detail="No eres dueño de este taller")
                if commission.status not in ("PENDING",):
                    raise HTTPException(status_code=400, detail="La comisión no está pendiente de pago")

                commission.status = "PENDING_VERIFICATION"
                commission.payment_method = body.get("payment_method", "OTHER")
                commission.reference_number = body.get("reference_number")
                if body.get("rate") is not None:
                    commission.rate = body["rate"]
                if body.get("rate_date"):
                    try:
                        from datetime import datetime
                        commission.rate_date = datetime.fromisoformat(body["rate_date"])
                    except ValueError:
                        pass
                await session.commit()

            # Notify superadmin
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_registered_admin
                from src.config.models import User as _U, UserRole as _UR
                from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID as _RMAP
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _sa = (await _s.execute(_sel(_U).join(_UR, _UR.user_id == _U.id).where(_UR.role_id == _RMAP["SUPERADMIN"]))).scalars().first()
                    _owner = (await _s.execute(_sel(_U).where(_U.id == current_user.id))).scalars().first()
                    if _sa and _owner:
                        await send_email(
                            _sa.email,
                            "Pago de comisión registrado - AutoTech",
                            payment_registered_admin(
                                "Comisión de taller",
                                f"{_owner.first_name} {_owner.last_name}",
                                commission.commission_amount,
                                body.get("payment_method", "OTHER"),
                                body.get("reference_number"),
                                lang=_sa.language_preference or "es",
                            ),
                        )
            except Exception as e:
                import logging
                logging.error(f"Error sending email for commission payment {commission_id}: {e}")

            return CoreResponse(
                success=True,
                status_code=200,
                message="Pago registrado. Pendiente de verificación.",
            )

        @self._router.patch("/my-commissions/workshop/{workshop_id}/register-payment-all", response_model=CoreResponse)
        async def register_all_my_commissions_payment(
            workshop_id: UUID,
            body: dict,
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            from src.config.database import get_session
            from src.config.models import WorkshopCommission as WCModel, Workshop as WorkshopModel
            from sqlalchemy import select

            async with get_session() as session:
                ws = await session.get(WorkshopModel, workshop_id)
                if not ws or ws.owner_id != current_user.id:
                    raise HTTPException(status_code=403, detail="No eres dueño de este taller")

                stmt = select(WCModel).where(
                    WCModel.workshop_id == workshop_id,
                    WCModel.status == "PENDING",
                )
                r = await session.execute(stmt)
                commissions = r.scalars().all()
                if not commissions:
                    raise HTTPException(status_code=400, detail="No hay comisiones pendientes para este taller")

                total_amount = 0
                for comm in commissions:
                    comm.status = "PENDING_VERIFICATION"
                    comm.payment_method = body.get("payment_method", "OTHER")
                    comm.reference_number = body.get("reference_number")
                    if body.get("rate") is not None:
                        comm.rate = body["rate"]
                    if body.get("rate_date"):
                        try:
                            from datetime import datetime
                            comm.rate_date = datetime.fromisoformat(body["rate_date"])
                        except ValueError:
                            pass
                    total_amount += comm.commission_amount
                await session.commit()

            # Notify superadmin
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_registered_admin
                from src.config.models import User as _U, UserRole as _UR
                from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID as _RMAP
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _sa = (await _s.execute(_sel(_U).join(_UR, _UR.user_id == _U.id).where(_UR.role_id == _RMAP["SUPERADMIN"]))).scalars().first()
                    _owner = (await _s.execute(_sel(_U).where(_U.id == current_user.id))).scalars().first()
                    if _sa and _owner:
                        await send_email(
                            _sa.email,
                            "Pago de comisión registrado - AutoTech",
                            payment_registered_admin(
                                "Comisión de taller",
                                f"{_owner.first_name} {_owner.last_name}",
                                total_amount,
                                body.get("payment_method", "OTHER"),
                                body.get("reference_number"),
                                lang=_sa.language_preference or "es",
                            ),
                        )
            except Exception as e:
                import logging
                logging.error(f"Error sending superadmin commission notification email: {e}")

            return CoreResponse(
                success=True,
                status_code=200,
                message=f"Pago registrado para {len(commissions)} comisiones. Total: ${total_amount:.2f}. Pendiente de verificación.",
            )

        @self._router.patch("/my-commissions/register-payment-all", response_model=CoreResponse)
        async def register_all_workshops_commissions_payment(
            body: dict,
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            from src.config.database import get_session
            from src.config.models import WorkshopCommission as WCModel, Workshop as WorkshopModel
            from sqlalchemy import select

            async with get_session() as session:
                ws_stmt = select(WorkshopModel.id).where(WorkshopModel.owner_id == current_user.id)
                ws_r = await session.execute(ws_stmt)
                ws_ids = [r[0] for r in ws_r.all()]
                if not ws_ids:
                    raise HTTPException(status_code=400, detail="No tienes talleres registrados")

                stmt = select(WCModel).where(
                    WCModel.workshop_id.in_(ws_ids),
                    WCModel.status == "PENDING",
                )
                r = await session.execute(stmt)
                commissions = r.scalars().all()
                if not commissions:
                    raise HTTPException(status_code=400, detail="No hay comisiones pendientes")

                total_amount = 0
                for comm in commissions:
                    comm.status = "PENDING_VERIFICATION"
                    comm.payment_method = body.get("payment_method", "OTHER")
                    comm.reference_number = body.get("reference_number")
                    if body.get("rate") is not None:
                        comm.rate = body["rate"]
                    if body.get("rate_date"):
                        try:
                            from datetime import datetime
                            rate_date = datetime.fromisoformat(body["rate_date"])
                            comm.rate_date = rate_date
                            comm.paid_at = rate_date
                        except ValueError:
                            pass
                    total_amount += comm.commission_amount
                await session.commit()

            # Notify superadmin
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_registered_admin
                from src.config.models import User as _U, UserRole as _UR
                from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID as _RMAP
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _sa = (await _s.execute(_sel(_U).join(_UR, _UR.user_id == _U.id).where(_UR.role_id == _RMAP["SUPERADMIN"]))).scalars().first()
                    _owner = (await _s.execute(_sel(_U).where(_U.id == current_user.id))).scalars().first()
                    if _sa and _owner:
                        await send_email(
                            _sa.email,
                            "Pago de comisión registrado - AutoTech",
                            payment_registered_admin(
                                "Comisión de taller",
                                f"{_owner.first_name} {_owner.last_name}",
                                total_amount,
                                body.get("payment_method", "OTHER"),
                                body.get("reference_number"),
                                lang=_sa.language_preference or "es",
                            ),
                        )
            except Exception as e:
                import logging
                logging.error(f"Error sending superadmin commission notification email: {e}")

            return CoreResponse(
                success=True,
                status_code=200,
                message=f"Pago registrado para {len(commissions)} comisiones de todos tus talleres. Total: ${total_amount:.2f}. Pendiente de verificación.",
            )

        @self._router.get("/{id}", response_model=CoreResponse[WorkshopDTO])
        async def get_workshop(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.get_by_id(id)
            handle_service_result(result, response)
            return result

        @self._router.put("/{id}", response_model=CoreResponse[WorkshopDTO])
        async def update_workshop(
            id: UUID,
            response: Response,
            name: str | None = Form(None),
            address: str | None = Form(None),
            latitude: float | None = Form(None),
            longitude: float | None = Form(None),
            verification_document: UploadFile | None = File(None),
            photo: UploadFile | None = File(None),
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            body = UpdateWorkshopRequest(
                name=name,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
            doc_url = None
            if verification_document:
                doc_url = await save_upload_file(
                    verification_document, "verification_documents"
                )
            photo_url = None
            if photo:
                photo_url = await save_upload_file(photo, "workshop_photos")
            result = await service.update(id, body, user_id, doc_url, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}", response_model=CoreResponse)
        async def delete_workshop(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.delete(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/{id}/toggle-suspension",
            response_model=CoreResponse[WorkshopDTO],
            status_code=200,
        )
        async def toggle_workshop_suspension(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.toggle_suspension(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post("/{id}/photo", response_model=CoreResponse[WorkshopDTO])
        async def upload_workshop_photo(
            id: UUID,
            response: Response,
            photo: UploadFile = File(...),
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            photo_url = await save_upload_file(photo, "workshop_photos")
            result = await service.upload_photo(id, user_id, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}/photo", response_model=CoreResponse[WorkshopDTO])
        async def delete_workshop_photo(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.delete_photo(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{id}/verification",
            response_model=CoreResponse[WorkshopDTO],
        )
        async def get_workshop_verification(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            _: CurrentUser = Depends(require_admin),
        ):
            result = await service.get_by_id_admin(id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/{id}/certify",
            response_model=CoreResponse[WorkshopDTO],
            status_code=200,
        )
        async def certify_workshop(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            _: CurrentUser = Depends(require_admin),
        ):
            result = await service.certify(id)
            handle_service_result(result, response)
            return result

        # -- Bank Accounts --

        @self._router.post(
            "/{workshop_id}/bank-accounts",
            response_model=CoreResponse[BankAccountDTO],
            status_code=201,
        )
        async def create_bank_account(
            workshop_id: UUID,
            body: CreateBankAccountRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.create_bank_account(
                workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{workshop_id}/bank-accounts",
            response_model=CoreResponse[BankAccountListDTO],
        )
        async def list_bank_accounts(
            workshop_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.list_bank_accounts(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/{workshop_id}/bank-accounts/{account_id}",
            response_model=CoreResponse[BankAccountDTO],
        )
        async def update_bank_account(
            workshop_id: UUID,
            account_id: UUID,
            body: UpdateBankAccountRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_bank_account(
                account_id, workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.delete(
            "/{workshop_id}/bank-accounts/{account_id}",
            response_model=CoreResponse,
        )
        async def delete_bank_account(
            workshop_id: UUID,
            account_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.delete_bank_account(
                account_id, workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        # -- Mobile Payments --

        @self._router.post(
            "/{workshop_id}/mobile-payments",
            response_model=CoreResponse[MobilePaymentDTO],
            status_code=201,
        )
        async def create_mobile_payment(
            workshop_id: UUID,
            body: CreateMobilePaymentRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.create_mobile_payment(
                workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{workshop_id}/mobile-payments",
            response_model=CoreResponse[MobilePaymentListDTO],
        )
        async def list_mobile_payments(
            workshop_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.list_mobile_payments(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/{workshop_id}/mobile-payments/{payment_id}",
            response_model=CoreResponse[MobilePaymentDTO],
        )
        async def update_mobile_payment(
            workshop_id: UUID,
            payment_id: UUID,
            body: UpdateMobilePaymentRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_mobile_payment(
                payment_id, workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.delete(
            "/{workshop_id}/mobile-payments/{payment_id}",
            response_model=CoreResponse,
        )
        async def delete_mobile_payment(
            workshop_id: UUID,
            payment_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.delete_mobile_payment(
                payment_id, workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        # -- Payment Methods --

        @self._router.post(
            "/{workshop_id}/payment-methods",
            response_model=CoreResponse[PaymentMethodDTO],
            status_code=201,
        )
        async def create_payment_method(
            workshop_id: UUID,
            body: CreatePaymentMethodRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.create_payment_method(
                workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{workshop_id}/payment-methods",
            response_model=CoreResponse[PaymentMethodListDTO],
        )
        async def list_payment_methods(
            workshop_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.list_payment_methods(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/{workshop_id}/payment-methods/{method_id}",
            response_model=CoreResponse[PaymentMethodDTO],
        )
        async def update_payment_method(
            workshop_id: UUID,
            method_id: UUID,
            body: UpdatePaymentMethodRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_payment_method(
                method_id, workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.delete(
            "/{workshop_id}/payment-methods/{method_id}",
            response_model=CoreResponse,
        )
        async def delete_payment_method(
            workshop_id: UUID,
            method_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.delete_payment_method(
                method_id, workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        # -- Ratings --

        @self._router.post(
            "/{workshop_id}/ratings",
            response_model=CoreResponse[None],
            status_code=201,
        )
        async def rate_workshop(
            workshop_id: UUID,
            body: RateWorkshopRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.rate_workshop(workshop_id, user_id, body)
            handle_service_result(result, response)
            return result

