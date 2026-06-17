import bcrypt
from typing import Type
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.users.infrastructure.mapper import UserMapper
from src.modules.users.application.create import CreateUserRequest, UserDTO
from src.modules.users.domain.entity import User
from src.modules.users.infrastructure.repository import UserRepository


class UserService:
    __mapper = UserMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

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
                role="CLIENT",
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
            content=UserDTO.model_validate(self.__mapper.to_entity(u_model)),
        )


def get_user_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> UserService:
    return UserService(transaction)
