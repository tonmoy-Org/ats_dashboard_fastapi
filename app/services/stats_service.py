import aiosqlite
from typing import Dict, Any

class StatsService:
    @staticmethod
    async def get_dashboard_stats(db: aiosqlite.Connection) -> Dict[str, Any]:
        async with db.execute("SELECT COUNT(*) as total FROM accounts") as c_master:
            r_master = await c_master.fetchone()
            master_total = r_master["total"] if r_master else 0

        async with db.execute("SELECT COUNT(*) as total FROM accounts_trade") as c_trade:
            r_trade = await c_trade.fetchone()
            trade_total = r_trade["total"] if r_trade else 0

        async with db.execute("SELECT COUNT(*) as total FROM target_numbers") as c_target:
            r_target = await c_target.fetchone()
            target_total = r_target["total"] if r_target else 0

        async with db.execute("SELECT COUNT(*) as total FROM target_numbers WHERE status = 'inactive'") as c_target_inactive:
            r_target_inactive = await c_target_inactive.fetchone()
            target_inactive = r_target_inactive["total"] if r_target_inactive else 0

        async with db.execute("SELECT COUNT(*) as total FROM account_cookies") as c_cookies:
            r_cookies = await c_cookies.fetchone()
            cookies_total = r_cookies["total"] if r_cookies else 0

        # Recent 10 master accounts
        async with db.execute(
            """
            SELECT a.id, a.email, a.password, a.status, a.row_focus, a.timestamp, u.username as owner, a.full_data
            FROM accounts a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.id DESC
            LIMIT 10
            """
        ) as cursor:
            recent_rows = await cursor.fetchall()
            recent = [dict(row) for row in recent_rows]

        return {
            "success": True,
            "data": {
                "master_accounts": master_total,
                "trade_accounts": trade_total,
                "target_numbers_total": target_total,
                "target_numbers_inactive": target_inactive,
                "cookies_total": cookies_total,
                "recent_accounts": recent
            }
        }
