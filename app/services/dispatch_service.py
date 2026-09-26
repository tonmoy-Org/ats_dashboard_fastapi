import re
import aiosqlite
from typing import Dict, Any, Optional

CARRIER_MAP = {
    "jio": "jio", "reliance": "jio", "rjio": "jio",
    "airtel": "airtel", "bharti": "airtel",
    "vi": "vodafone_idea", "vodafone": "vodafone_idea", "idea": "vodafone_idea", "vodafone_idea": "vodafone_idea",
    "bsnl": "bsnl", "ais": "ais", "dtac": "dtac", "truemove": "truemove"
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

class DispatchService:
    @staticmethod
    async def get_stats(db: aiosqlite.Connection, country: str = "IN") -> Dict[str, Any]:
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

    @staticmethod
    async def dispatch_number(
        db: aiosqlite.Connection,
        country: str = "IN",
        pool_type: str = "new",
        carrier: str = "any",
        circle: str = "any",
        rdp_id: str = "bot_worker"
    ) -> Dict[str, Any]:
        carrier_norm = normalize_carrier(carrier)
        circle_norm = normalize_circle(circle)

        query = "SELECT * FROM target_numbers WHERE country = ? AND status = 'inactive'"
        sql_params = [country]

        if pool_type != "any":
            query += " AND pool_type = ?"
            sql_params.append(pool_type)

        if carrier_norm != "any":
            query += " AND operator = ?"
            sql_params.append(carrier_norm)

        if circle_norm != "any":
            query += " AND circle = ?"
            sql_params.append(circle_norm)

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

    @staticmethod
    async def report_outcome(db: aiosqlite.Connection, params: Dict[str, Any]) -> Dict[str, Any]:
        phone_or_id = str(params.get("phone", params.get("number", params.get("id", "")))).strip()
        status_val = str(params.get("status", params.get("outcome", params.get("step_status", "completed")))).lower().strip()
        password = str(params.get("password", params.get("password_hint", ""))).strip()
        full_data = str(params.get("full_data", params.get("data", ""))).strip()
        rdp_id = str(params.get("rdp_id", params.get("bot_id", "bot_worker"))).strip()

        digits = re.sub(r'\D+', '', phone_or_id)

        if digits:
            await db.execute(
                """
                UPDATE target_numbers 
                SET status = ?, password_hint = CASE WHEN ? != '' THEN ? ELSE password_hint END, updated_at = CURRENT_TIMESTAMP 
                WHERE phone LIKE ? OR id = ?
                """,
                (status_val, password, password, f"%{digits}%", digits)
            )

        email_or_phone = str(params.get("email", phone_or_id)).strip()
        if email_or_phone and (password or full_data or status_val):
            user_id = int(params.get("user_id", 0))
            row_focus = "number" if "@" not in email_or_phone else "mail"
            
            await db.execute(
                """
                INSERT INTO accounts (user_id, email, password, status, full_data, row_focus)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email_or_phone, password, status_val, full_data, row_focus)
            )
            async with db.execute("SELECT last_insert_rowid()") as cursor:
                m_row = await cursor.fetchone()
                master_id = m_row[0] if m_row else 0

            await db.execute(
                """
                INSERT INTO accounts_trade (master_account_id, user_id, email, password, status, full_data, row_focus)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email, row_focus) DO UPDATE SET
                    password = excluded.password,
                    status = excluded.status,
                    full_data = excluded.full_data,
                    timestamp = CURRENT_TIMESTAMP
                """,
                (master_id, user_id, email_or_phone, password, status_val, full_data, row_focus)
            )

        await db.commit()
        return {"success": True, "status": "updated", "phone": phone_or_id, "outcome": status_val}

    @staticmethod
    async def batch_fetch(
        db: aiosqlite.Connection,
        country: str = "IN",
        pool_type: str = "new",
        carrier: str = "any",
        circle: str = "any",
        limit: int = 20,
        rdp_id: str = "bot_worker"
    ) -> Dict[str, Any]:
        carrier_norm = normalize_carrier(carrier)
        circle_norm = normalize_circle(circle)

        query = "SELECT * FROM target_numbers WHERE status = 'inactive'"
        sql_params = []

        if country and country != "ALL":
            query += " AND country = ?"
            sql_params.append(country)

        if pool_type != "any":
            query += " AND pool_type = ?"
            sql_params.append(pool_type)

        if carrier_norm != "any":
            query += " AND operator = ?"
            sql_params.append(carrier_norm)

        if circle_norm != "any":
            query += " AND circle = ?"
            sql_params.append(circle_norm)

        query += " ORDER BY updated_at ASC, id ASC LIMIT ?"
        sql_params.append(limit)

        async with db.execute(query, tuple(sql_params)) as cursor:
            rows = await cursor.fetchall()
            items = [dict(r) for r in rows]

        if items:
            ids = [r["id"] for r in items]
            placeholders = ",".join(["?"] * len(ids))
            await db.execute(
                f"UPDATE target_numbers SET status = 'running', assigned_rdp = ?, assigned_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                [rdp_id] + ids
            )
            await db.commit()

        return {
            "success": True,
            "count": len(items),
            "data": items,
            "numbers": items
        }

    @staticmethod
    async def omni_search(db: aiosqlite.Connection, query_text: str) -> Dict[str, Any]:
        q = query_text.strip()
        if not q:
            return {"success": False, "error": "Query text is required"}

        async with db.execute("SELECT * FROM target_numbers WHERE phone LIKE ? LIMIT 50", (f"%{q}%",)) as c_t:
            targets = [dict(row) for row in await c_t.fetchall()]

        async with db.execute("SELECT * FROM accounts WHERE email LIKE ? OR full_data LIKE ? LIMIT 50", (f"%{q}%", f"%{q}%")) as c_a:
            accounts = [dict(row) for row in await c_a.fetchall()]

        return {
            "success": True,
            "query": q,
            "target_numbers": targets,
            "accounts": accounts
        }
