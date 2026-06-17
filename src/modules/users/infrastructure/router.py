from fastapi import Depends, APIRouter, Response
from src.core.infrastructure.router import BaseRouter
from src.modules.users.infrastructure.service import UserService, get_user_service
from src.utils.handle_service_result import handle_service_result
from src.modules.users.application.create import CreateUserRequest


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
