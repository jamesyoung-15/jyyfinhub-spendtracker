"""FastAPI App entry point"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jyyfinhub_spendtracker.api import api_router
from jyyfinhub_spendtracker.core.config import get_settings
from jyyfinhub_spendtracker.core.exceptions import SpendTrackerError
from jyyfinhub_spendtracker.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    yield


async def domain_error_handler(
    request: Request, exc: SpendTrackerError
) -> JSONResponse:
    """Translate domain exceptions into the API error contract"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        debug=settings.app_debug, title=settings.app_project_name, lifespan=lifespan
    )

    app.add_exception_handler(SpendTrackerError, domain_error_handler)  # type: ignore[arg-type]

    app.include_router(api_router)

    return app


app = create_app()
