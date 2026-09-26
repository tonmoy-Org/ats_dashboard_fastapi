from fastapi import APIRouter
import time
from app.core.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "db_path": settings.get_resolved_db_path(),
        "timestamp": time.time()
    }
