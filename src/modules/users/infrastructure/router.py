from uuid import UUID
from fastapi import Depends, APIRouter, HTTPException, Response, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.users.infrastructure.service import UserService, get_user_service
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.users.application.create import CreateUserRequest, UserDTO
from src.modules.users.application.login import LoginRequest, TokenResponse, TwoFactorSetupResponse, TwoFactorVerifyRequest
from src.modules.users.application.update import UpdateUserRequest, ChangePasswordRequest


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class UserRouter(BaseRouter):
    __prefix__ = "/users"
    __tag__ = "Users"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.post(
            "/register", response_model=CoreResponse[UserDTO], status_code=201
        )
        async def create(
            body: CreateUserRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
        ):
            result = await service.create(body)
            handle_service_result(result, response)
            return result

        @self._router.post("/token", response_model=TokenResponse)
        async def token(
            form: OAuth2PasswordRequestForm = Depends(),
            service: UserService = Depends(get_user_service),
        ):
            body = LoginRequest(email=form.username, password=form.password)
            result = await service.login(body)
            if not result or not result.success:
                raise HTTPException(
                    status_code=result.status_code, detail=result.message
                )
            return result.content

        @self._router.post(
            "/login", response_model=CoreResponse[TokenResponse], status_code=200
        )
        async def login(
            body: LoginRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
        ):
            result = await service.login(body)
            handle_service_result(result, response)
            return result

        @self._router.get("/me", response_model=CoreResponse[UserDTO])
        async def me(
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_me(user_id)
            handle_service_result(result, response)
            return result

        @self._router.put("/me", response_model=CoreResponse[UserDTO])
        async def update_me(
            body: UpdateUserRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.update(user_id, body)
            handle_service_result(result, response)
            return result

        @self._router.post("/me/change-password", response_model=CoreResponse)
        async def change_password(
            body: ChangePasswordRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.change_password(user_id, body)
            handle_service_result(result, response)
            return result

        @self._router.post("/me/2fa/setup", response_model=CoreResponse[TwoFactorSetupResponse])
        async def setup_2fa(
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.setup_2fa(user_id)
            handle_service_result(result, response)
            return result

        @self._router.post("/me/2fa/verify", response_model=CoreResponse)
        async def verify_2fa(
            body: TwoFactorVerifyRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.verify_2fa(user_id, body.code)
            handle_service_result(result, response)
            return result

        @self._router.post("/me/2fa/disable", response_model=CoreResponse)
        async def disable_2fa(
            body: TwoFactorVerifyRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.disable_2fa(user_id, body.code)
            handle_service_result(result, response)
            return result

        @self._router.put("/me/photo", response_model=CoreResponse[UserDTO])
        async def upload_profile_photo(
            photo: UploadFile = File(...),
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            from src.utils.file_upload import save_upload_file
            from src.modules.users.infrastructure.user_dto_helper import user_to_dto
            photo_url = await save_upload_file(photo, "profile_photos")
            user_model = await service.update_profile(user_id, photo_url=photo_url)
            return CoreResponse(success=True, status_code=200, message="Foto actualizada", content=user_to_dto(user_model))

        @self._router.delete("/me/photo", response_model=CoreResponse[UserDTO])
        async def delete_profile_photo(
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            from src.modules.users.infrastructure.user_dto_helper import user_to_dto
            user_model = await service.update_profile(user_id, photo_url=None)
            return CoreResponse(success=True, status_code=200, message="Foto eliminada", content=user_to_dto(user_model))

        @self._router.post("/forgot-password", response_model=CoreResponse)
        async def forgot_password(
            body: ForgotPasswordRequest,
            response: Response,
        ):
            from src.modules.users.infrastructure.repository import UserRepository
            from src.config.database import get_session
            from src.utils.email import send_email
            from src.config.settings import settings
            from src.config.models import UserRole as UserRoleModel
            from sqlalchemy import select as sa_select

            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get_by_email(body.email)
                if not user:
                    response.status_code = 404
                    return CoreResponse(success=False, status_code=404, message="No existe una cuenta registrada con este correo.", content=None)

                # Check roles — only CLIENT and WORKSHOP_OWNER can reset password
                from src.config.models import Role as RoleModel
                roles_stmt = sa_select(RoleModel.name).join(
                    UserRoleModel, UserRoleModel.role_id == RoleModel.id
                ).where(UserRoleModel.user_id == user.id)
                r = await session.execute(roles_stmt)
                roles = [row[0] for row in r.all()]

                if "ADMIN" in roles or "SUPERADMIN" in roles:
                    response.status_code = 403
                    return CoreResponse(success=False, status_code=403, message="Por seguridad, los administradores no pueden recuperar la contraseña por esta vía.", content=None)

                import jwt
                from datetime import datetime, timedelta
                reset_token = jwt.encode(
                    {"sub": str(user.id), "type": "password_reset", "exp": datetime.utcnow() + timedelta(hours=1)},
                    settings.SECRET_KEY,
                    algorithm="HS256",
                )
                link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
                from src.utils.email_templates import password_recovery
                await send_email(
                    body.email,
                    "Recuperación de contraseña - AutoTech",
                    password_recovery(body.email, link, lang=user.language_preference or "es"),
                )
            return CoreResponse(success=True, status_code=200, message="Se ha enviado un enlace de recuperación a tu correo.", content=None)

        @self._router.post("/reset-password", response_model=CoreResponse)
        async def reset_password(
            body: ResetPasswordRequest,
        ):
            import jwt
            from jwt import PyJWTError
            from src.config.database import get_session
            from src.config.settings import settings
            from src.modules.users.infrastructure.repository import UserRepository
            try:
                payload = jwt.decode(body.token, settings.SECRET_KEY, algorithms=["HS256"])
                if payload.get("type") != "password_reset":
                    raise ValueError("Invalid token type")
                user_id = UUID(payload["sub"])
            except (PyJWTError, ValueError, Exception):
                raise HTTPException(status_code=400, detail="Token inválido o expirado")

            import bcrypt
            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get(str(user_id))
                if not user:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")
                user.password_hash = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                session.add(user)
                await session.commit()
            return CoreResponse(success=True, status_code=200, message="Contraseña restablecida correctamente", content=None)
