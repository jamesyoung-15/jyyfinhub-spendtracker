"""Aggregate every HTML page router."""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER

from jyyfinhub_spendtracker.web.payment_methods import router as payment_methods_router
from jyyfinhub_spendtracker.web.transactions import router as transactions_router

router = APIRouter(include_in_schema=False)


@router.get("/")
async def home() -> RedirectResponse:
    return RedirectResponse("/transactions", status_code=HTTP_303_SEE_OTHER)


router.include_router(transactions_router)
router.include_router(payment_methods_router)
