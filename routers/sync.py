from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Any, List, Optional, Union
import re
import random
import asyncio
import aiosqlite
import requests

from database import get_async_db
from config import ATS_API_BEARER

router = APIRouter(tags=["Sync"])

def extract_phone(full_data: str) -> Optional[str]:
    match = re.search(r'(?:91)?[6-9]\d{9}', full_data)
    if match:
        digits = re.sub(r'\D+', '', match.group(0))
        return digits[-10:]
    return None

def detect_carrier(phone: str) -> str:
    # Basic carrier mapping heuristic
    prefix = phone[:4] if len(phone) >= 4 else ""
    if prefix in ["9820", "9821", "9892", "9967", "9819"]:
        return "airtel"
    elif prefix in ["9833", "9820", "9702"]:
        return "jio"
    return "airtel"

def detect_circle(phone: str) -> str:
    return "telangana"

@router.post("/api_sync.php")
@router.post("/api/sync")
async def api_sync(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_async_db)
):
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    
    raw_body = await request.body()
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    if not token:
        token = data.get("token") or data.get("secret") or request.query_params.get("token", "")
        
    if token != ATS_API_BEARER:
        return {"success": False, "error": "Unauthorized"}
    
    user_id = int(data.get("user_id", 0))
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()
    status = str(data.get("status", "")).strip()
    full_data = str(data.get("full_data", "")).strip()
    row_focus = str(data.get("row_focus", "mail")).strip()
    
    if not email or not password:
        return {"success": False, "error": "Email and password are required"}

    # Fetch user role
    async with db.execute("SELECT role FROM users WHERE id = ?", (user_id,)) as cursor:
        user_row = await cursor.fetchone()
    user_role = user_row["role"] if user_row else "client"

    # Transactional retry block
    for attempt in range(15):
        try:
            # 1. Master Vault Insertion
            await db.execute(
                """
                INSERT INTO accounts (user_id, email, password, status, full_data, row_focus)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, password, status, full_data, row_focus)
            )
            
            async with db.execute("SELECT last_insert_rowid()") as cursor:
                master_id_row = await cursor.fetchone()
            master_id = master_id_row[0]
            
            # 2. Active Trade Pool Insertion (Upsert on email, row_focus)
            await db.execute(
                """
                INSERT INTO accounts_trade (master_account_id, user_id, email, password, status, full_data, row_focus)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email, row_focus) DO UPDATE SET
                    master_account_id = excluded.master_account_id,
                    user_id = excluded.user_id,
                    password = excluded.password,
                    status = excluded.status,
                    full_data = excluded.full_data,
                    timestamp = CURRENT_TIMESTAMP
                """,
                (master_id, user_id, email, password, status, full_data, row_focus)
            )
            
            # 3. Interim Purge for Completed Accounts
            is_completed = ("complete" in status.lower() or "recover" in status.lower())
            if is_completed and "@" in email:
                await db.execute(
                    """
                    DELETE FROM accounts_trade 
                    WHERE master_account_id IN (
                        SELECT id FROM accounts WHERE password = ? AND email NOT LIKE '%@%' AND id != ?
                    )
                    """,
                    (password, master_id)
                )
                await db.execute(
                    "DELETE FROM accounts WHERE password = ? AND email NOT LIKE '%@%' AND id != ?",
                    (password, master_id)
                )
                
                ph_digits = extract_phone(full_data)
                if ph_digits:
                    ph91 = f"91{ph_digits}"
                    await db.execute("DELETE FROM target_numbers WHERE phone = ? OR phone = ?", (ph_digits, ph91))
                    await db.execute(
                        """
                        DELETE FROM accounts_trade 
                        WHERE master_account_id IN (
                            SELECT id FROM accounts WHERE (email = ? OR email = ?) AND id != ?
                        )
                        """,
                        (ph_digits, ph91, master_id)
                    )
                    await db.execute("DELETE FROM accounts WHERE (email = ? OR email = ?) AND id != ?", (ph_digits, ph91, master_id))

            # 4. Target Number Status Updates
            clean_phone = re.sub(r'[^\d]', '', email)
            if len(clean_phone) == 10 and clean_phone[0] in ['6', '7', '8', '9']:
                clean_phone = f"91{clean_phone}"
                
            if len(clean_phone) == 12 and clean_phone.startswith("91"):
                if is_completed:
                    await db.execute("DELETE FROM target_numbers WHERE phone = ?", (clean_phone,))
                else:
                    async with db.execute("SELECT id, password_hint FROM target_numbers WHERE phone = ? LIMIT 1", (clean_phone,)) as cursor:
                        t_row = await cursor.fetchone()
                    if t_row:
                        t_id, existing_hint = t_row["id"], t_row["password_hint"] or ""
                        hints = [h.strip() for h in re.split(r'[|,\t]+', existing_hint) if h.strip()]
                        if password and password not in hints:
                            hints.append(password)
                        merged_hints = " | ".join(dict.fromkeys(hints))
                        await db.execute(
                            """
                            UPDATE target_numbers 
                            SET password_hint = ?, status = 'inactive', pool_type = 'old', assigned_rdp = NULL, assigned_at = NULL, updated_at = CURRENT_TIMESTAMP 
                            WHERE id = ?
                            """,
                            (merged_hints, t_id)
                        )
                    else:
                        op = detect_carrier(clean_phone)
                        cir = detect_circle(clean_phone)
                        await db.execute(
                            """
                            INSERT OR IGNORE INTO target_numbers (phone, password_hint, operator, circle, status, created_at, updated_at) 
                            VALUES (?, ?, ?, ?, 'inactive', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """,
                            (clean_phone, password, op, cir)
                        )
            
            await db.commit()
            break
        except aiosqlite.OperationalError as oe:
            if attempt == 14:
                raise oe
            await asyncio.sleep(random.uniform(0.03, 0.09))

    return {"success": True, "message": "Account synced successfully"}
