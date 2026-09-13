"""Aggregate every domain router"""

from fastapi import APIRouter

from jyyfinhub_spendtracker.payment_methods.router import (
    router as payment_method_router,
)
from jyyfinhub_spendtracker.transaction_templates.router import (
    router as transaction_template_router,
)
from jyyfinhub_spendtracker.transactions.router import router as transaction_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(payment_method_router)
api_router.include_router(transaction_router)
api_router.include_router(transaction_template_router)
