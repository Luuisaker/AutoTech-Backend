from uuid import UUID
from fastapi import Depends, APIRouter, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.users.infrastructure.service import UserService, get_user_service
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.users.application.create import CreateUserRequest, UserDTO
from src.modules.users.application.login import LoginRequest, TokenResponse
from src.modules.users.application.update import UpdateUserRequest, ChangePasswordRequest


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
