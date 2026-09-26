from fastapi import APIRouter, Depends, Header, HTTPException, Request
import json
import aiosqlite
from typing import Optional

from database import get_async_db
from config import ATS_API_BEARER

router = APIRouter(tags=["Cookies"])

@router.api_route("/api_cookies.php", methods=["GET", "POST", "OPTIONS"])
@router.api_route("/api/cookies", methods=["GET", "POST", "OPTIONS"])
async def api_cookies(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_async_db)
):
    if request.method == "OPTIONS":
        return {"status": "ok"}

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
        token = str(params.get("token", params.get("secret", "")))

    if token != ATS_API_BEARER:
        raise HTTPException(status_code=401, detail="Unauthorized")

    action = str(params.get("action", "store")).lower().strip()

    # 1. Store / Save Cookies
    if action in ["store", "save"]:
        email = str(params.get("email", "")).strip()
        cookies_json = str(params.get("cookies_json", "")).strip()
        cookies_netscape = str(params.get("cookies_netscape", "")).strip()
        cookie_count = int(params.get("cookie_count", 0))
        admin_user = str(params.get("admin_user", "admin")).strip()
        login_ip = str(params.get("login_ip", "")).strip()

        if not email:
            return {"success": False, "error": "Email is required"}

        if cookie_count == 0 and cookies_json:
            try:
                parsed = json.loads(cookies_json)
                if isinstance(parsed, list):
                    cookie_count = len(parsed)
            except Exception:
                pass

        await db.execute(
            """
            INSERT INTO account_cookies (email, cookies_json, cookies_netscape, cookie_count, admin_user, login_ip, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                cookies_json = excluded.cookies_json,
                cookies_netscape = excluded.cookies_netscape,
                cookie_count = excluded.cookie_count,
                admin_user = excluded.admin_user,
                login_ip = excluded.login_ip,
                updated_at = CURRENT_TIMESTAMP
            """,
            (email, cookies_json, cookies_netscape, cookie_count, admin_user, login_ip)
        )
        await db.commit()

        return {
            "success": True,
            "status": "ok",
            "email": email,
            "cookie_count": cookie_count
        }

    # 2. Get / Fetch Cookies by Email
    elif action in ["get", "fetch"]:
        email = str(params.get("email", "")).strip()
        if not email:
            return {"success": False, "error": "Email is required"}

        async with db.execute("SELECT * FROM account_cookies WHERE email = ? LIMIT 1", (email,)) as cursor:
            row = await cursor.fetchone()

        if row:
            return {
                "success": True,
                "has_cookie": True,
                "data": dict(row)
            }
        else:
            return {
                "success": True,
                "has_cookie": False,
                "message": "No cookies found for email"
            }

    # 3. List / Summary Cookies
    elif action in ["list", "summary"]:
        limit = min(100, max(1, int(params.get("limit", 25))))
        page = max(1, int(params.get("page", 1)))
        offset = (page - 1) * limit

        async with db.execute("SELECT COUNT(*) as total FROM account_cookies") as c_total:
            r_total = await c_total.fetchone()
            total = r_total["total"] if r_total else 0

        async with db.execute(
            "SELECT id, email, cookie_count, admin_user, login_ip, status, updated_at FROM account_cookies ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            items = [dict(row) for row in rows]

        return {
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "items": items
        }

    return {"success": False, "error": f"Unknown action: {action}"}
