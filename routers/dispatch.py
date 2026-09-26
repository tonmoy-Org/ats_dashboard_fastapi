from fastapi import APIRouter, Depends, Request
import aiosqlite
from typing import Optional, Dict, Any

from database import get_async_db

router = APIRouter(tags=["Dispatch"])

CARRIER_MAP = {
    "jio": "jio", "reliance": "jio", "rjio": "jio",
    "airtel": "airtel", "bharti": "airtel",
    "vi": "vodafone_idea", "vodafone": "vodafone_idea", "idea": "vodafone_idea", "vodafone_idea": "vodafone_idea",
    "bsnl": "bsnl",
    "ais": "ais", "dtac": "dtac", "truemove": "truemove"
}

def normalize_carrier(c: str) -> str:
    c = c.lower().strip()
    if not c or c in ["all", "auto", "any"]:
        return "any"
    return CARRIER_MAP.get(c, c)

def normalize_circle(c: str) -> str:
    c = c.lower().strip()
    if not c or c in ["all", "auto", "any"]:
        return "any"
    return c.replace(" ", "_").replace("-", "_")

@router.api_route("/api_dispatch.php", methods=["GET", "POST"])
@router.api_route("/api/dispatch", methods=["GET", "POST"])
async def api_dispatch(request: Request, db: aiosqlite.Connection = Depends(get_async_db)):
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update(body)
        except Exception:
            form = await request.form()
            params.update(dict(form))

    action = str(params.get("action", "stats")).lower().strip()
    country = str(params.get("country", "IN")).upper().strip()
    if country in ["", "ALL"]:
        country = "IN"

    # 1. Stats Action
    if action in ["stats", "pool_counts_quick", "get_stats", "get_stock_summary"]:
        async with db.execute("SELECT COUNT(*) as total FROM target_numbers WHERE country = ?", (country,)) as c1:
            r1 = await c1.fetchone()
            total_target = r1["total"] if r1 else 0

        async with db.execute("SELECT COUNT(*) as total FROM target_numbers WHERE country = ? AND status = 'inactive'", (country,)) as c2:
            r2 = await c2.fetchone()
            inactive_target = r2["total"] if r2 else 0

        async with db.execute("SELECT COUNT(*) as total FROM pool_numbers WHERE country = ?", (country,)) as c3:
            r3 = await c3.fetchone()
            total_pool = r3["total"] if r3 else 0

        return {
            "success": True,
            "country": country,
            "target_numbers_total": total_target,
            "target_numbers_inactive": inactive_target,
            "pool_numbers_total": total_pool
        }

    # 2. Dispatch Action
    elif action in ["dispatch", "get_number", "claim"]:
        pool_type = str(params.get("pool_type", "new")).lower().strip()
        carrier = normalize_carrier(str(params.get("carrier", params.get("operator", "any"))))
        circle = normalize_circle(str(params.get("circle", "any")))
        rdp_id = str(params.get("rdp_id", params.get("assigned_rdp", "bot_worker")))

        query = "SELECT * FROM target_numbers WHERE country = ? AND status = 'inactive'"
        sql_params = [country]

        if pool_type != "any":
            query += " AND pool_type = ?"
            sql_params.append(pool_type)

        if carrier != "any":
            query += " AND operator = ?"
            sql_params.append(carrier)

        if circle != "any":
            query += " AND circle = ?"
            sql_params.append(circle)

        query += " ORDER BY updated_at ASC, id ASC LIMIT 1"

        async with db.execute(query, tuple(sql_params)) as cursor:
            number_row = await cursor.fetchone()

        if number_row:
            row_dict = dict(number_row)
            await db.execute(
                "UPDATE target_numbers SET status = 'running', assigned_rdp = ?, assigned_at = CURRENT_TIMESTAMP WHERE id = ?",
                (rdp_id, row_dict["id"])
            )
            await db.commit()
            return {
                "success": True,
                "found": True,
                "data": {
                    "id": row_dict["id"],
                    "phone": row_dict["phone"],
                    "password_hint": row_dict.get("password_hint", ""),
                    "operator": row_dict.get("operator", ""),
                    "circle": row_dict.get("circle", ""),
                    "pool_type": row_dict.get("pool_type", "new"),
                    "country": row_dict.get("country", "IN")
                }
            }
        else:
            return {"success": True, "found": False, "message": "No numbers available for dispatch matching filter"}

    # 3. Omni Search Action
    elif action in ["omni_search", "search"]:
        q = str(params.get("q", params.get("query", ""))).strip()
        if not q:
            return {"success": False, "error": "Query parameter 'q' is required"}

        async with db.execute(
            "SELECT * FROM target_numbers WHERE phone LIKE ? LIMIT 50", (f"%{q}%",)
        ) as c_t:
            targets = [dict(row) for row in await c_t.fetchall()]

        async with db.execute(
            "SELECT * FROM accounts WHERE email LIKE ? OR full_data LIKE ? LIMIT 50", (f"%{q}%", f"%{q}%")
        ) as c_a:
            accounts = [dict(row) for row in await c_a.fetchall()]

        return {
            "success": True,
            "query": q,
            "target_numbers": targets,
            "accounts": accounts
        }

    return {"success": False, "error": f"Unknown action: {action}"}
