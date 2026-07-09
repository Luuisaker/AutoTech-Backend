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
from src.modules.users.application.login import LoginRequest, TokenResponse
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

        @self._router.put("/me/photo", response_model=CoreResponse[UserDTO])
        async def upload_profile_photo(
            photo: UploadFile = File(...),
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            from src.utils.file_upload import save_upload_file
            from src.modules.users.infrastructure.mapper import UserMapper
            photo_url = await save_upload_file(photo, "profile_photos")
            user_model = await service.update_profile(user_id, photo_url=photo_url)
            user_entity = UserMapper().to_entity(user_model)
            return CoreResponse(success=True, status_code=200, message="Foto actualizada", content=UserDTO.model_validate(user_entity))

        @self._router.delete("/me/photo", response_model=CoreResponse[UserDTO])
        async def delete_profile_photo(
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            from src.modules.users.infrastructure.mapper import UserMapper
            user_model = await service.update_profile(user_id, photo_url=None)
            user_entity = UserMapper().to_entity(user_model)
            return CoreResponse(success=True, status_code=200, message="Foto eliminada", content=UserDTO.model_validate(user_entity))

        @self._router.post("/forgot-password", response_model=CoreResponse)
        async def forgot_password(
            body: ForgotPasswordRequest,
        ):
            from src.modules.users.infrastructure.repository import UserRepository
            from src.config.database import get_session
            from src.utils.email import send_email
            from src.config.settings import settings

            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get_by_email(body.email)
                if user:
                    import jwt
                    from datetime import datetime, timedelta
                    reset_token = jwt.encode(
                        {"sub": str(user.id), "type": "password_reset", "exp": datetime.utcnow() + timedelta(hours=1)},
                        settings.SECRET_KEY,
                        algorithm="HS256",
                    )
                    link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
                    await send_email(
                        body.email,
                        "Recuperación de contraseña - AutoTech",
                        f'<p>Haz clic en el siguiente enlace para restablecer tu contraseña:</p><p><a href="{link}">{link}</a></p><p>Este enlace expira en 1 hora.</p>',
                    )
            return CoreResponse(success=True, status_code=200, message="Si el correo está registrado, recibirás un enlace de recuperación.", content=None)

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
