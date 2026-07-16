from uuid import UUID

import bcrypt
from typing import Type
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.users.infrastructure.mapper import UserMapper
from src.modules.users.application.create import CreateUserRequest, UserDTO
from src.modules.users.application.login import LoginRequest, TokenResponse, TwoFactorSetupResponse, TwoFactorVerifyRequest
from src.modules.users.application.update import UpdateUserRequest, ChangePasswordRequest
from src.modules.users.domain.entity import User
from src.modules.users.infrastructure.auth import create_access_token, ROLE_UUID_TO_NAME
from src.modules.users.infrastructure.repository import UserRepository


class UserService:
    __mapper = UserMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    def _user_to_dto(self, user_model) -> UserDTO:
        entity = self.__mapper.to_entity(user_model)
        dto = UserDTO.model_validate(entity)
        dto.parts_available = entity.parts_credit_limit - entity.total_parts_debt
        dto.service_available = entity.service_credit_limit - entity.total_service_debt
        return dto

    async def create(self, dto: CreateUserRequest) -> Response:
        password_bytes = dto.password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

        async with self._transaction(user=UserRepository) as t:
            if await t.user.get_by_email(dto.email):
                return Response(
                    status_code=400,
                    success=False,
                    message="El email ya está registrado",
                )

            if await t.user.get_by_ci(dto.ci):
                return Response(
                    status_code=400,
                    success=False,
                    message="La cédula ya está registrada",
                )

            user_entity = User(
                email=dto.email,
                password_hash=hashed_password,
                roles=[dto.role.value],
                first_name=dto.first_name,
                last_name=dto.last_name,
                ci=dto.ci,
                phone=dto.phone,
            )

            u_model = await t.user.add(self.__mapper.to_model(user_entity))

        return Response(
            status_code=201,
            success=True,
            message="Usuario creado exitosamente",
            content=self._user_to_dto(u_model),
        )

    async def login(self, dto: LoginRequest) -> Response:
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get_by_email(dto.email)

        if not user_model or user_model.deleted_at is not None:
            return Response(
                status_code=401,
                success=False,
                message="Contraseña o correo incorrecto",
            )

        if user_model.is_suspended:
            return Response(
                status_code=403,
                success=False,
                message="Tu cuenta ha sido suspendida temporalmente. Contacta al Servicio Técnico.",
            )

        if not bcrypt.checkpw(
            dto.password.encode("utf-8"),
            user_model.password_hash.encode("utf-8"),
        ):
            return Response(
                status_code=401,
                success=False,
                message="Contraseña o correo incorrecto",
            )

        roles = [ROLE_UUID_TO_NAME.get(str(ur.role_id), "CLIENT") for ur in user_model.roles]

        # Check 2FA if enabled
        if user_model.is_2fa_enabled:
            # Check if this is a trusted device
            from src.config.models import TrustedDevice as _TD
            from sqlalchemy import select as _sel
            is_trusted = False
            if dto.device_id:
                async with self._transaction(user=UserRepository) as _t2:
                    _td_stmt = _sel(_TD).where(
                        _TD.user_id == user_model.id,
                        _TD.device_id == dto.device_id,
                    )
                    _td_r = await _t2.user._session.execute(_td_stmt)
                    is_trusted = _td_r.scalars().first() is not None

            if not is_trusted:
                if not dto.totp_code:
                    return Response(
                        status_code=401,
                        success=False,
                        message="Se requiere código de autenticación de dos factores",
                    )
                import pyotp
                if not user_model.totp_secret:
                    return Response(
                        status_code=401,
                        success=False,
                        message="2FA configurado incorrectamente. Contacta al administrador.",
                    )
                totp = pyotp.TOTP(user_model.totp_secret)
                if not totp.verify(dto.totp_code):
                    return Response(
                        status_code=401,
                        success=False,
                        message="Código de autenticación incorrecto",
                    )

                # Trust this device after successful 2FA
                if dto.device_id:
                    async with self._transaction(user=UserRepository) as _t3:
                        _td = _TD(
                            user_id=user_model.id,
                            device_id=dto.device_id,
                        )
                        _t3.user._session.add(_td)
                        await _t3.user._session.commit()

        token = create_access_token(user_model.id, roles)

        return Response(
            status_code=200,
            success=True,
            content=TokenResponse(access_token=token),
            message="Inicio de sesión exitoso",
        )

    async def get_me(self, user_id: UUID) -> Response:
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))

        if not user_model:
            return Response(
                status_code=404,
                success=False,
                message="Usuario no encontrado",
            )

        return Response(
            status_code=200,
            success=True,
            content=self._user_to_dto(user_model),
        )

    async def update(self, user_id: UUID, dto: UpdateUserRequest) -> Response:
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))
            if not user_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Usuario no encontrado",
                )

            if dto.first_name is not None:
                user_model.first_name = dto.first_name
            if dto.last_name is not None:
                user_model.last_name = dto.last_name
            if dto.phone is not None:
                user_model.phone = dto.phone
            if dto.language_preference is not None:
                user_model.language_preference = dto.language_preference

            user_model = await t.user.update(user_model)

        return Response(
            status_code=200,
            success=True,
            message="Usuario actualizado exitosamente",
            content=self._user_to_dto(user_model),
        )

    async def update_profile(self, user_id: UUID, *, photo_url: str | None = None) -> User:
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))
            if not user_model:
                raise ValueError("Usuario no encontrado")
            user_model.photo_url = photo_url
            user_model = await t.user.update(user_model)
        return user_model

    async def change_password(
        self, user_id: UUID, dto: ChangePasswordRequest
    ) -> Response:
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))
            if not user_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Usuario no encontrado",
                )

            if not bcrypt.checkpw(
                dto.current_password.encode("utf-8"),
                user_model.password_hash.encode("utf-8"),
            ):
                return Response(
                    status_code=401,
                    success=False,
                    message="Contraseña actual incorrecta",
                )

            password_bytes = dto.new_password.encode("utf-8")
            salt = bcrypt.gensalt()
            user_model.password_hash = bcrypt.hashpw(password_bytes, salt).decode("utf-8")
            await t.user.update(user_model)

        return Response(
            status_code=200,
            success=True,
            message="Contraseña actualizada exitosamente",
        )

    async def setup_2fa(self, user_id: UUID) -> Response:
        import pyotp
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))
            if not user_model:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            if user_model.is_2fa_enabled:
                return Response(status_code=400, success=False, message="2FA ya está activado")

            secret = pyotp.random_base32()
            user_model.totp_secret = secret
            await t.user.update(user_model)

            totp = pyotp.TOTP(secret)
            issuer = "AutoTech"
            account = user_model.email
            otpauth_uri = totp.provisioning_uri(name=account, issuer_name=issuer)

        return Response(
            status_code=200,
            success=True,
            message="Secreto 2FA generado. Verifica con tu app autenticadora.",
            content=TwoFactorSetupResponse(secret=secret, otpauth_uri=otpauth_uri),
        )

    async def verify_2fa(self, user_id: UUID, code: str) -> Response:
        import pyotp
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))
            if not user_model:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            if not user_model.totp_secret:
                return Response(status_code=400, success=False, message="Primero debes configurar 2FA")

            if user_model.is_2fa_enabled:
                return Response(status_code=400, success=False, message="2FA ya está activado")

            totp = pyotp.TOTP(user_model.totp_secret)
            if not totp.verify(code):
                return Response(status_code=400, success=False, message="Código incorrecto")

            user_model.is_2fa_enabled = 1
            await t.user.update(user_model)

        return Response(
            status_code=200,
            success=True,
            message="Autenticación de dos factores activada",
        )

    async def disable_2fa(self, user_id: UUID, code: str) -> Response:
        import pyotp
        async with self._transaction(user=UserRepository) as t:
            user_model = await t.user.get(str(user_id))
            if not user_model:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            if not user_model.is_2fa_enabled:
                return Response(status_code=400, success=False, message="2FA no está activado")

            totp = pyotp.TOTP(user_model.totp_secret)
            if not totp.verify(code):
                return Response(status_code=400, success=False, message="Código incorrecto")

            user_model.is_2fa_enabled = 0
            user_model.totp_secret = None
            await t.user.update(user_model)

        return Response(
            status_code=200,
            success=True,
            message="Autenticación de dos factores desactivada",
        )


def get_user_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> UserService:
    return UserService(transaction)
