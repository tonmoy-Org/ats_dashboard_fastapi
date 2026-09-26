from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import time
from datetime import datetime
from passlib.hash import bcrypt
import aiosqlite

from database import get_async_db
from config import ATS_SUPER_SECRET

router = APIRouter(tags=["Auth"])

class AuthRequest(BaseModel):
    secret: Optional[str] = ""
    username: str
    password: str
    hwid: Optional[str] = ""

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.verify(plain_password, hashed_password)
    except Exception:
        # Fallback for plain comparison or simple hashes
        return plain_password == hashed_password

@router.post("/api_auth.php")
@router.post("/api/auth/login")
async def api_auth(payload: AuthRequest, db: aiosqlite.Connection = Depends(get_async_db)):
    if payload.secret and payload.secret != ATS_SUPER_SECRET:
        return {"status": "error", "message": "Unauthorized access."}
    
    if not payload.username.strip() or not payload.password:
        return {"status": "error", "message": "Username and password required."}
    
    async with db.execute("SELECT * FROM users WHERE username = ?", (payload.username.strip(),)) as cursor:
        user = await cursor.fetchone()
        
    if not user:
        return {"status": "error", "message": "Invalid Username or Password."}
    
    user_dict = dict(user)
    
    if not verify_password(payload.password, user_dict["password_hash"]):
        return {"status": "error", "message": "Invalid Username or Password."}
    
    # Check Expiry
    if user_dict.get("role") != "admin" and user_dict.get("expiry_date"):
        try:
            exp_str = str(user_dict["expiry_date"])
            exp_time = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S").timestamp()
            if time.time() > exp_time:
                return {"status": "error", "message": "Subscription Expired! Contact Admin."}
        except Exception:
            pass

    # Check HWID Binding
    if user_dict.get("role") != "admin" and payload.hwid:
        current_hwid = user_dict.get("hwid")
        if not current_hwid:
            await db.execute("UPDATE users SET hwid = ? WHERE id = ?", (payload.hwid, user_dict["id"]))
            await db.commit()
        elif current_hwid != payload.hwid:
            return {"status": "error", "message": "License is bound to another PC!"}

    return {
        "status": "success",
        "message": "License valid.",
        "role": user_dict.get("role", "client"),
        "user_id": user_dict["id"],
        "expiry_date": user_dict.get("expiry_date") or "Lifetime"
    }
