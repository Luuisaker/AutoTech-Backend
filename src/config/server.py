import os
import sys
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config.settings import settings
from src.utils.add_routers import add_routers

from src.modules.users.infrastructure.router import UserRouter
from src.modules.vehicles.infrastructure.router import VehicleRouter
from src.modules.workshops.infrastructure.router import WorkshopRouter

routers = [
    UserRouter(),
    VehicleRouter(),
    WorkshopRouter(),
]


class App:
    def __init__(self) -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self.server = FastAPI(
            title="AutoTech API",
            description="Backend API for AutoTech",
            version="1.0.0",
        )

        self._setup_middlewares()
        self._setup_base_routes()
        self._setup_static_files()

        add_routers(self.server, routers)

    def _setup_middlewares(self) -> None:
        origins = [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
        self.server.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_base_routes(self) -> None:
        @self.server.get("/health", tags=["Status"])
        async def health_check():
            return {"status": "ok", "message": "AutoTech API is running"}

    def _setup_static_files(self) -> None:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        self.server.mount(
            "/uploads",
            StaticFiles(directory=settings.UPLOAD_DIR),
            name="uploads",
        )
