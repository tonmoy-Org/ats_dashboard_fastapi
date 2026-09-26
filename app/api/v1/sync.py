from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Optional
import aiosqlite

from app.core.config import settings
from app.db.sqlite import get_db
from app.schemas.sync import SyncRequest, SyncResponse
from app.services.sync_service import SyncService

router = APIRouter(tags=["Sync"])

@router.post("/sync", response_model=SyncResponse)
@router.post("/api_sync.php", response_model=SyncResponse)
async def sync_account(
    request: Request,
    payload: SyncRequest,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = payload.secret or request.query_params.get("token", "")

    if token != settings.ATS_API_BEARER:
        return SyncResponse(success=False, error="Unauthorized")

    return await SyncService.process_account_sync(db, payload)
