"""FastAPI App entry point"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from jyyfinhub_spendtracker.api import api_router
from jyyfinhub_spendtracker.core.config import get_settings
from jyyfinhub_spendtracker.core.exceptions import SpendTrackerError
from jyyfinhub_spendtracker.core.logging import configure_logging
from jyyfinhub_spendtracker.web.routes import router as web_router
from jyyfinhub_spendtracker.web.templates import STATIC_DIR, templates


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    yield


async def domain_error_handler(request: Request, exc: SpendTrackerError) -> Response:
    """Translate domain exceptions for whichever surface raised them.

    One handler, two renderings: the API gets the error contract, the browser gets a page.
    """
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exc.status_code,
            "error_code": exc.error_code,
            "message": exc.message,
        },
        status_code=exc.status_code,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        debug=settings.app_debug, title=settings.app_project_name, lifespan=lifespan
    )

    app.add_exception_handler(SpendTrackerError, domain_error_handler)  # type: ignore[arg-type]

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api_router)
    app.include_router(web_router)

    return app


app = create_app()
