from fastapi import APIRouter, Depends, Request
import aiosqlite

from app.db.sqlite import get_db
from app.services.dispatch_service import DispatchService

router = APIRouter(tags=["Dispatch"])

@router.api_route("/dispatch", methods=["GET", "POST"])
@router.api_route("/api_dispatch.php", methods=["GET", "POST"])
async def dispatch_endpoint(request: Request, db: aiosqlite.Connection = Depends(get_db)):
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update(body)
        except Exception:
            form = await request.form()
            params.update(dict(form))

    has_action_param = "action" in params
    action = str(params.get("action", "batch_fetch" if not has_action_param else "dispatch")).lower().strip()
    country = str(params.get("country", "IN")).upper().strip()
    if country in ["", "ALL"]:
        country = "IN"

    if action in ["stats", "pool_counts_quick", "get_stats", "get_stock_summary"]:
        return await DispatchService.get_stats(db, country=country)

    elif action in ["dispatch", "get_number", "claim", "fetch_next"]:
        pool_type = str(params.get("pool_type", "new")).lower().strip()
        carrier = str(params.get("carrier", params.get("operator", "any")))
        circle = str(params.get("circle", "any"))
        rdp_id = str(params.get("rdp_id", params.get("assigned_rdp", "bot_worker")))
        return await DispatchService.dispatch_number(db, country, pool_type, carrier, circle, rdp_id)

    elif action in ["batch_fetch", "fetch_pool", "fetch_batch"]:
        pool_type = str(params.get("pool_type", "new")).lower().strip()
        carrier = str(params.get("carrier", params.get("operator", "any")))
        circle = str(params.get("circle", "any"))
        limit = int(params.get("limit", 20))
        rdp_id = str(params.get("rdp_id", params.get("assigned_rdp", "bot_worker")))
        return await DispatchService.batch_fetch(db, country, pool_type, carrier, circle, limit, rdp_id)

    elif action in ["report_outcome", "update_status", "report_status", "update_step_status", "upload_cookie"]:
        return await DispatchService.report_outcome(db, params)

    elif action in ["omni_search", "search"]:
        q = str(params.get("q", params.get("query", "")))
        return await DispatchService.omni_search(db, q)

    return {"success": False, "error": f"Unknown action: {action}"}
