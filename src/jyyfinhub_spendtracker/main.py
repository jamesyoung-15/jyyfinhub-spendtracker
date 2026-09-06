"""FastAPI App entry point"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from jyyfinhub_spendtracker.api import api_router
from jyyfinhub_spendtracker.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        debug=settings.app_debug, title=settings.app_project_name, lifespan=lifespan
    )

    app.include_router(api_router)

    return app


app = create_app()
