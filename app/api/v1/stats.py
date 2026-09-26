from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Optional
import aiosqlite

from app.core.config import settings
from app.db.sqlite import get_db
from app.services.stats_service import StatsService

router = APIRouter(tags=["Stats"])

@router.api_route("/api_v2_stats.php", methods=["GET", "POST"])
@router.api_route("/stats", methods=["GET", "POST"])
async def get_stats_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = str(request.query_params.get("token", ""))

    if token != settings.ATS_API_BEARER:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return await StatsService.get_dashboard_stats(db)
