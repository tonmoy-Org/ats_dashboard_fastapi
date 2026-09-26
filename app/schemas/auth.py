from pydantic import BaseModel, Field
from typing import Optional

class AuthRequest(BaseModel):
    secret: Optional[str] = Field(default="", description="Secret key for authentication")
    username: str = Field(..., description="User account username")
    password: str = Field(..., description="Account password")
    hwid: Optional[str] = Field(default="", description="Hardware ID for device binding")

class AuthResponse(BaseModel):
    status: str
    message: str
    role: Optional[str] = "client"
    user_id: Optional[int] = None
    expiry_date: Optional[str] = "Lifetime"
