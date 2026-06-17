import sys
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.utils.add_routers import add_routers

routers = []


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

        add_routers(self.server, routers)

    def _setup_middlewares(self) -> None:
        self.server.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_base_routes(self) -> None:
        @self.server.get("/health", tags=["Status"])
        async def health_check():
            return {"status": "ok", "message": "AutoTech API is running"}
