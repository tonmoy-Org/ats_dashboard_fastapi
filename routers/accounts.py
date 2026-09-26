from fastapi import APIRouter, Depends, Header, HTTPException, Request
import aiosqlite
from typing import Optional, Dict, Any

from database import get_async_db
from config import ATS_API_BEARER

router = APIRouter(tags=["Accounts"])

@router.api_route("/api_v2_accounts.php", methods=["GET", "POST"])
@router.api_route("/api/v2/accounts", methods=["GET", "POST"])
async def api_v2_accounts(request: Request, db: aiosqlite.Connection = Depends(get_async_db)):
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update(body)
        except Exception:
            form = await request.form()
            params.update(dict(form))

    pool = str(params.get("pool", "trade")).lower().strip()
    table_name = "accounts_trade" if pool == "trade" else "accounts"
    
    page = max(1, int(params.get("page", 1)))
    limit = min(500, max(1, int(params.get("limit", 25))))
    offset = (page - 1) * limit
    
    focus = str(params.get("focus", "mail")).lower().strip()
    role = str(params.get("role", "all")).lower().strip()
    search = str(params.get("search", "")).strip()

    where_clauses = []
    sql_params = []

    if focus != "all":
        where_clauses.append("t.row_focus = ?")
        sql_params.append(focus)

    if role != "all":
        where_clauses.append("u.role = ?")
        sql_params.append(role)

    if search:
        where_clauses.append("(t.email LIKE ? OR t.full_data LIKE ?)")
        sql_params.extend([f"%{search}%", f"%{search}%"])

    where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_query = f"SELECT COUNT(*) as total FROM {table_name} t LEFT JOIN users u ON t.user_id = u.id" + where_str
    async with db.execute(count_query, tuple(sql_params)) as c_count:
        r_count = await c_count.fetchone()
        total_records = r_count["total"] if r_count else 0

    data_query = f"""
        SELECT t.id, t.email, t.password, t.status, t.full_data, t.row_focus, t.timestamp, u.username as owner, u.role as user_role
        FROM {table_name} t
        LEFT JOIN users u ON t.user_id = u.id
        {where_str}
        ORDER BY t.id DESC
        LIMIT ? OFFSET ?
    """
    sql_params.extend([limit, offset])

    async with db.execute(data_query, tuple(sql_params)) as cursor:
        rows = await cursor.fetchall()
        records = [dict(row) for row in rows]

    return {
        "success": True,
        "data": {
            "total": total_records,
            "page": page,
            "limit": limit,
            "total_pages": (total_records + limit - 1) // max(1, limit),
            "pool": table_name,
            "focus": focus,
            "records": records
        }
    }


@router.api_route("/api_v2_actions.php", methods=["GET", "POST"])
@router.api_route("/api/v2/actions", methods=["GET", "POST"])
async def api_v2_actions(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_async_db)
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

    if token != ATS_API_BEARER:
        raise HTTPException(status_code=401, detail="Unauthorized")

    action = str(params.get("action", "")).lower().strip()

    if action == "clear_pool_role":
        role = str(params.get("role", "admin")).lower().strip()
        focus = str(params.get("focus", "mail")).lower().strip()
        
        delete_sql = """
            DELETE FROM accounts_trade 
            WHERE id IN (
                SELECT t.id FROM accounts_trade t 
                JOIN users u ON t.user_id = u.id 
                WHERE LOWER(u.role) = ? AND LOWER(t.row_focus) = ?
            )
        """
        async with db.execute(delete_sql, (role, focus)) as cursor:
            deleted = cursor.rowcount
        await db.commit()

        return {
            "success": True,
            "message": f"Successfully cleared {deleted} {focus} records for role {role} from Active Work Pool! Master Lifetime Vault (accounts) is 100% safe & untouched.",
            "deleted_count": deleted
        }

    elif action == "clear_pool_user":
        user_id = int(params.get("user_id", 0))
        focus = str(params.get("focus", "mail")).lower().strip()
        if user_id <= 0:
            return {"success": False, "error": "Invalid user ID"}

        async with db.execute("DELETE FROM accounts_trade WHERE user_id = ? AND LOWER(row_focus) = ?", (user_id, focus)) as cursor:
            deleted = cursor.rowcount
        await db.commit()

        return {
            "success": True,
            "message": f"Cleared {deleted} {focus} records from Working Pool! Master Archive is 100% safe.",
            "deleted_count": deleted
        }

    elif action == "reset_running":
        async with db.execute("UPDATE accounts_trade SET status = 'selection' WHERE status IN ('running', 'in_progress', 'processing')") as cursor:
            affected = cursor.rowcount
        await db.commit()

        return {
            "success": True,
            "message": f"Successfully reset {affected} stuck running records back to selection pool!",
            "modifiedCount": affected
        }

    return {"success": False, "error": f"Unknown action: {action}"}
