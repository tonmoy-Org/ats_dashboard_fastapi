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

def format_target_record(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    record_id = row_dict.get("id", 0)
    phone_raw = str(row_dict.get("phone", "")).strip()
    clean_digits = re.sub(r'\D+', '', phone_raw)
    if len(clean_digits) == 10 and clean_digits[0] in '6789':
        phone_full = f"91{clean_digits}"
    else:
        phone_full = clean_digits if clean_digits else phone_raw

    password = str(row_dict.get("password_hint", "") or row_dict.get("password", "")).strip()
    operator = str(row_dict.get("operator", "airtel")).lower().strip()
    circle = str(row_dict.get("circle", "telangana")).lower().strip()
    pool_type = str(row_dict.get("pool_type", "new")).lower().strip()
    country = str(row_dict.get("country", "IN")).upper().strip()
    status = str(row_dict.get("status", "inactive")).upper().strip()

    prefix = clean_digits[:4] if len(clean_digits) >= 4 else ""
    old_data = f"{phone_full}\t{password}\t{operator}\t{circle}"

    op_display = "Vi (Vodafone Idea)" if operator in ["vi", "vodafone_idea", "vodafone", "idea"] else operator.title()
    circle_display = circle.replace("_", " ").title()

    return {
        "id": record_id,
        "target_id": record_id,
        "pool_record_id": record_id,
        "number_id": record_id,
        "phone": phone_full,
        "number": phone_full,
        "email": phone_full,
        "target_number": phone_full,
        "password": password,
        "password_hint": password,
        "pass": password,
        "recovery_email": "",
        "auth_key": "",
        "backup_codes": "",
        "old_data": old_data,
        "country": country,
        "carrier": operator,
        "operator": operator,
        "pool_carrier": operator,
        "circle": circle,
        "pool_circle": circle,
        "pool_type": pool_type,
        "status": status,
        "tier": 1,
        "sister_fallback": False,
        "engine": "FastAPI-SQLite-Engine",
        "telecom": {
            "operator": operator,
            "operatorName": op_display,
            "circle": circle,
            "circleName": circle_display,
            "prefix": prefix
        }
    }

class DispatchService:
    @staticmethod
    async def get_stats(db: aiosqlite.Connection, country: str = "IN") -> Dict[str, Any]:
        country_filter = "WHERE country = ?" if country and country != "ALL" else "WHERE 1=1"
        country_params = (country,) if country and country != "ALL" else ()

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter}", country_params) as cursor:
            r = await cursor.fetchone()
            total_target = r[0] if r else 0

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter} AND status = 'inactive'", country_params) as cursor:
            r = await cursor.fetchone()
            inactive_target = r[0] if r else 0

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter} AND status = 'running'", country_params) as cursor:
            r = await cursor.fetchone()
            running_target = r[0] if r else 0

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter} AND status IN ('completed', 'done')", country_params) as cursor:
            r = await cursor.fetchone()
            completed_target = r[0] if r else 0

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter} AND status IN ('failed', 'dead')", country_params) as cursor:
            r = await cursor.fetchone()
            failed_target = r[0] if r else 0

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter} AND pool_type = 'new' AND status = 'inactive'", country_params) as cursor:
            r = await cursor.fetchone()
            new_pool_count = r[0] if r else 0

        async with db.execute(f"SELECT COUNT(*) FROM target_numbers {country_filter} AND pool_type = 'old' AND status = 'inactive'", country_params) as cursor:
            r = await cursor.fetchone()
            old_pool_count = r[0] if r else 0

        # Breakdown by operator
        breakdown = {}
        async with db.execute(f"SELECT operator, COUNT(*) as cnt FROM target_numbers {country_filter} AND status = 'inactive' GROUP BY operator", country_params) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                op_name = str(row["operator"]).lower().strip()
                breakdown[op_name] = row["cnt"]

        stats_dict = {
            "total": total_target,
            "new_pool": new_pool_count,
            "old_pool": old_pool_count,
            "ready": inactive_target,
            "inactive": inactive_target,
            "running": running_target,
            "done": completed_target,
            "completed": completed_target,
            "failed": failed_target,
            "dead": failed_target
        }

        return {
            "success": True,
            "status": "success",
            "country": country,
            "total": total_target,
            "total_new_pool": new_pool_count,
            "total_old_pool": old_pool_count,
            "ready": inactive_target,
            "new_pool": new_pool_count,
            "old_pool": old_pool_count,
            "running": running_target,
            "done": completed_target,
            "completed": completed_target,
            "failed": failed_target,
            "dead": failed_target,
            "breakdown": breakdown,
            "stats": stats_dict,
            "data": stats_dict
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

        base_query = "SELECT * FROM target_numbers WHERE status = 'inactive'"
        base_params = []

        if country and country != "ALL":
            base_query += " AND country = ?"
            base_params.append(country)

        if pool_type != "any":
            base_query += " AND pool_type = ?"
            base_params.append(pool_type)

        query = base_query
        sql_params = list(base_params)

        if carrier_norm != "any":
            query += " AND operator = ?"
            sql_params.append(carrier_norm)

        if circle_norm != "any":
            query += " AND circle = ?"
            sql_params.append(circle_norm)

        query += " ORDER BY updated_at ASC, id ASC LIMIT 1"

        async with db.execute(query, tuple(sql_params)) as cursor:
            number_row = await cursor.fetchone()

        is_fallback = False
        if not number_row and (carrier_norm != "any" or circle_norm != "any"):
            fallback_query = base_query + " ORDER BY updated_at ASC, id ASC LIMIT 1"
            async with db.execute(fallback_query, tuple(base_params)) as cursor:
                number_row = await cursor.fetchone()
                if number_row:
                    is_fallback = True

        if number_row:
            row_dict = dict(number_row)
            await db.execute(
                "UPDATE target_numbers SET status = 'running', assigned_rdp = ?, assigned_at = CURRENT_TIMESTAMP WHERE id = ?",
                (rdp_id, row_dict["id"])
            )
            await db.commit()
            formatted = format_target_record(row_dict)
            if is_fallback:
                formatted["sister_fallback"] = True
            return {
                "success": True,
                "status": "success",
                "has_target": True,
                "found": True,
                "target": formatted,
                "data": formatted,
                "number": formatted,
                "targets": [formatted]
            }
        else:
            return {
                "success": True,
                "status": "empty",
                "has_target": False,
                "found": False,
                "targets": [],
                "message": "No numbers available for dispatch matching filter"
            }

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

        base_query = "SELECT * FROM target_numbers WHERE status = 'inactive'"
        base_params = []

        if country and country != "ALL":
            base_query += " AND country = ?"
            base_params.append(country)

        if pool_type != "any":
            base_query += " AND pool_type = ?"
            base_params.append(pool_type)

        query = base_query
        sql_params = list(base_params)

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

        is_fallback = False
        if not items and (carrier_norm != "any" or circle_norm != "any"):
            fallback_query = base_query + " ORDER BY updated_at ASC, id ASC LIMIT ?"
            fallback_params = list(base_params) + [limit]
            async with db.execute(fallback_query, tuple(fallback_params)) as cursor:
                rows = await cursor.fetchall()
                items = [dict(r) for r in rows]
                if items:
                    is_fallback = True

        if items:
            ids = [r["id"] for r in items]
            placeholders = ",".join(["?"] * len(ids))
            await db.execute(
                f"UPDATE target_numbers SET status = 'running', assigned_rdp = ?, assigned_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                [rdp_id] + ids
            )
            await db.commit()

        formatted_items = [format_target_record(r) for r in items]
        if is_fallback:
            for item in formatted_items:
                item["sister_fallback"] = True

        has_target = len(formatted_items) > 0

        return {
            "success": True,
            "status": "success" if has_target else "empty",
            "has_target": has_target,
            "count": len(formatted_items),
            "data": formatted_items,
            "targets": formatted_items,
            "numbers": formatted_items
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
