from uuid import UUID
from fastapi import Depends, APIRouter, Response
from src.core.infrastructure.router import BaseRouter
from src.modules.users.infrastructure.service import UserService, get_user_service
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.users.application.create import CreateUserRequest
from src.modules.users.application.login import LoginRequest


class UserRouter(BaseRouter):
    __prefix__ = "/users"
    __tag__ = "Users"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.post("/register", status_code=201)
        async def create(
            body: CreateUserRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
        ):
            result = await service.create(body)
            handle_service_result(result, response)
            return result

        @self._router.post("/login", status_code=200)
        async def login(
            body: LoginRequest,
            response: Response,
            service: UserService = Depends(get_user_service),
        ):
            result = await service.login(body)
            handle_service_result(result, response)
            return result

        @self._router.get("/me")
        async def me(
            response: Response,
            service: UserService = Depends(get_user_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_me(user_id)
            handle_service_result(result, response)
            return result
