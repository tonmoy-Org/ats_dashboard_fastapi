import sqlite3
import aiosqlite
from typing import AsyncGenerator
from app.core.config import settings

def get_sync_db_connection() -> sqlite3.Connection:
    db_path = settings.get_resolved_db_path()
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn

async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    db_path = settings.get_resolved_db_path()
    async with aiosqlite.connect(db_path, timeout=60.0) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = OFF;")
        await db.execute("PRAGMA busy_timeout = 60000;")
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        await db.execute("PRAGMA cache_size = -64000;")
        await db.execute("PRAGMA mmap_size = 268435456;")
        await db.execute("PRAGMA temp_store = MEMORY;")
        yield db

def init_db_schema() -> None:
    conn = get_sync_db_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'client',
            hwid TEXT,
            expiry_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            status TEXT NOT NULL,
            full_data TEXT,
            row_focus TEXT NOT NULL DEFAULT 'mail',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS accounts_trade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_account_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            status TEXT NOT NULL,
            full_data TEXT,
            row_focus TEXT NOT NULL DEFAULT 'mail',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (master_account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS target_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hint TEXT,
            operator TEXT DEFAULT 'airtel',
            circle TEXT DEFAULT 'telangana',
            status TEXT DEFAULT 'inactive',
            assigned_rdp TEXT,
            assigned_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            pool_type TEXT DEFAULT 'new',
            country TEXT DEFAULT 'IN'
        );

        CREATE TABLE IF NOT EXISTS pool_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL,
            password TEXT DEFAULT '',
            recovery_email TEXT DEFAULT '',
            auth_key TEXT DEFAULT '',
            backup_codes TEXT DEFAULT '',
            old_data TEXT DEFAULT '',
            country TEXT DEFAULT 'IN',
            carrier TEXT DEFAULT 'any',
            circle TEXT DEFAULT 'all',
            pool_type TEXT DEFAULT 'new',
            status TEXT DEFAULT 'READY',
            locked_by TEXT DEFAULT NULL,
            recovery_status TEXT DEFAULT NULL,
            result_data TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS account_cookies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT UNIQUE,
            password TEXT,
            cookies_json TEXT,
            cookies_netscape TEXT,
            cookie_count INTEGER DEFAULT 0,
            admin_user TEXT DEFAULT 'admin',
            login_ip TEXT,
            status TEXT DEFAULT 'Active',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("SELECT COUNT(*) FROM target_numbers")
    r = cursor.fetchone()
    if not r or r[0] == 0:
        carriers = ["airtel", "jio", "vodafone_idea", "bsnl"]
        circles = ["telangana", "maharashtra", "delhi", "karnataka", "up_east", "west_bengal", "gujarat", "punjab"]
        rows = []
        for i in range(1, 151):
            num = f"9198300{i:05d}"
            op = carriers[i % len(carriers)]
            cir = circles[i % len(circles)]
            ptype = "new" if i <= 100 else "old"
            rows.append((num, f"pass_{i:04d}", op, cir, "inactive", ptype, "IN"))
        cursor.executemany(
            """
            INSERT OR IGNORE INTO target_numbers (phone, password_hint, operator, circle, status, pool_type, country)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )

    conn.commit()
    conn.close()
