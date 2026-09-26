from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Optional
import aiosqlite

from app.core.config import settings
from app.db.sqlite import get_db

router = APIRouter(tags=["Completed Accounts"])

@router.api_route("/api_Completed_Account.php", methods=["GET", "POST"])
@router.api_route("/completed-accounts", methods=["GET", "POST"])
async def api_completed_account(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update(body)
        except Exception:
            form = await request.form()
            params.update(dict(form))

    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = str(params.get("token", params.get("secret", "")))

    if token != settings.ATS_API_BEARER:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = str(params.get("pool", "trade")).lower().strip()
    table = "accounts_trade" if pool == "trade" else "accounts"
    
    page = max(1, int(params.get("page", params.get("p", 1))))
    limit = min(500, max(1, int(params.get("limit", params.get("length", 50)))))
    offset = (page - 1) * limit
    search = str(params.get("q", params.get("search", ""))).strip()

    where_clauses = ["a.row_focus = 'mail'"]
    sql_params = []

    if search:
        where_clauses.append("(a.email LIKE ? OR a.password LIKE ? OR a.full_data LIKE ?)")
        sql_params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where_str = " WHERE " + " AND ".join(where_clauses)

    count_query = f"SELECT COUNT(*) as total FROM {table} a LEFT JOIN users u ON a.user_id = u.id" + where_str
    async with db.execute(count_query, tuple(sql_params)) as c_count:
        r_count = await c_count.fetchone()
        total_records = r_count["total"] if r_count else 0

    data_query = f"""
        SELECT a.id, a.user_id, u.username as worker, a.email, a.password, a.status, a.full_data, a.timestamp
        FROM {table} a
        LEFT JOIN users u ON a.user_id = u.id
        {where_str}
        ORDER BY a.id DESC
        LIMIT ? OFFSET ?
    """
    sql_params.extend([limit, offset])

    async with db.execute(data_query, tuple(sql_params)) as cursor:
        rows = await cursor.fetchall()
        records = [dict(row) for row in rows]

    return {
        "success": True,
        "pool": pool,
        "page": page,
        "limit": limit,
        "total_records": total_records,
        "total_pages": (total_records + limit - 1) // max(1, limit),
        "count": len(records),
        "data": records
    }
