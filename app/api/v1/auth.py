from fastapi import APIRouter, Depends
import aiosqlite

from app.db.sqlite import get_db
from app.schemas.auth import AuthRequest, AuthResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["Auth"])

@router.post("/auth/login", response_model=AuthResponse)
@router.post("/api_auth.php", response_model=AuthResponse)
async def login(payload: AuthRequest, db: aiosqlite.Connection = Depends(get_db)):
    return await AuthService.authenticate_user(db, payload)
