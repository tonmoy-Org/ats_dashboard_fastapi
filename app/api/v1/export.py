from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Optional
import aiosqlite

from app.core.config import settings
from app.db.sqlite import get_db

router = APIRouter(tags=["Export"])

@router.api_route("/api_export.php", methods=["GET", "POST"])
@router.api_route("/export", methods=["GET", "POST"])
async def api_export(
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

    async with db.execute("SELECT id, username FROM users WHERE role = 'admin'") as c_admins:
        admin_rows = await c_admins.fetchall()
        admins = {row["id"]: row["username"] for row in admin_rows}

    if not admins:
        return {"success": True, "completed": [], "verification": []}

    admin_ids = tuple(admins.keys())
    placeholders = ",".join("?" for _ in admin_ids)

    # Mail Focus (Completed)
    query_mail = f"SELECT full_data, email, status, user_id FROM accounts_trade WHERE user_id IN ({placeholders}) AND row_focus = 'mail' ORDER BY timestamp DESC"
    async with db.execute(query_mail, admin_ids) as c_mail:
        mail_rows = await c_mail.fetchall()
        completed = [dict(row) for row in mail_rows]

    # Number Focus (Verification)
    query_num = f"SELECT full_data, email, status, user_id FROM accounts_trade WHERE user_id IN ({placeholders}) AND row_focus = 'number' ORDER BY timestamp DESC"
    async with db.execute(query_num, admin_ids) as c_num:
        num_rows = await c_num.fetchall()
        verification = [dict(row) for row in num_rows]

    return {
        "success": True,
        "completed": completed,
        "verification": verification
    }
