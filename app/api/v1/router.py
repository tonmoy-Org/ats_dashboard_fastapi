from fastapi import APIRouter
from app.api.v1 import (
    auth, sync, dispatch, accounts, cookies, stats, login_success,
    completed_account, verification_number, export, health
)

api_router = APIRouter()

# Register API v1 sub-routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sync.router)
api_router.include_router(dispatch.router)
api_router.include_router(accounts.router)
api_router.include_router(cookies.router)
api_router.include_router(stats.router)
api_router.include_router(login_success.router)
api_router.include_router(completed_account.router)
api_router.include_router(verification_number.router)
api_router.include_router(export.router)
