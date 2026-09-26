from pydantic import BaseModel, Field
from typing import Optional

class SyncRequest(BaseModel):
    user_id: int = Field(default=0, description="User ID performing sync")
    email: str = Field(..., description="Recovered account email or phone number")
    password: str = Field(..., description="Account password")
    status: str = Field(..., description="Recovery status (e.g. Complete, Failed)")
    full_data: Optional[str] = Field(default="", description="Full TSV or JSON data payload")
    row_focus: Optional[str] = Field(default="mail", description="Data focus type ('mail' or 'number')")
    secret: Optional[str] = Field(default="", description="Bearer token or secret")

class SyncResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
