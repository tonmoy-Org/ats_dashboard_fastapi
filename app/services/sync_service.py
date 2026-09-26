import re
import random
import asyncio
import aiosqlite
from typing import Optional

from app.schemas.sync import SyncRequest, SyncResponse

def extract_phone(full_data: str) -> Optional[str]:
    match = re.search(r'(?:91)?[6-9]\d{9}', full_data)
    if match:
        digits = re.sub(r'\D+', '', match.group(0))
        return digits[-10:]
    return None

class SyncService:
    @staticmethod
    async def process_account_sync(db: aiosqlite.Connection, payload: SyncRequest) -> SyncResponse:
        user_id = payload.user_id
        email = payload.email.strip()
        password = payload.password.strip()
        status = payload.status.strip()
        full_data = (payload.full_data or "").strip()
        row_focus = (payload.row_focus or "mail").strip()
        
        if not email or not password:
            return SyncResponse(success=False, error="Email and password are required")

        # Retry loop for concurrency WAL locks
        for attempt in range(15):
            try:
                # 1. Master Vault Entry
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
                
                # 2. Active Trade Pool Entry (Upsert on email, row_focus)
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
                
                # 3. Automatic Interim Record Purge
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

                # 4. Target Number Cleanup & Re-queueing
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
                            await db.execute(
                                """
                                INSERT OR IGNORE INTO target_numbers (phone, password_hint, operator, circle, status, created_at, updated_at) 
                                VALUES (?, ?, 'airtel', 'telangana', 'inactive', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """,
                                (clean_phone, password)
                            )
                
                await db.commit()
                break
            except aiosqlite.OperationalError as oe:
                if attempt == 14:
                    raise oe
                await asyncio.sleep(random.uniform(0.03, 0.09))

        return SyncResponse(success=True, message="Account synced successfully")
