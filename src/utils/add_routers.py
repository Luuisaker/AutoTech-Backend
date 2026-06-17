from fastapi import FastAPI
from typing import Sequence
from src.core.infrastructure.router import BaseRouter


def add_routers(app: FastAPI, routers: Sequence[BaseRouter]) -> None:
    for instance in routers:
        router = instance.get_router()
        app.include_router(router)
