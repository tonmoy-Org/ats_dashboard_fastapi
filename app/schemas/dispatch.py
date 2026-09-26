from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class DispatchQuery(BaseModel):
    action: str = Field(default="stats", description="Action type (stats, dispatch, search)")
    country: Optional[str] = Field(default="IN", description="Country code (IN, TH, etc.)")
    pool_type: Optional[str] = Field(default="new", description="Pool type (new, old, any)")
    carrier: Optional[str] = Field(default="any", description="Telecom operator/carrier")
    circle: Optional[str] = Field(default="any", description="Telecom circle region")
    rdp_id: Optional[str] = Field(default="bot_worker", description="Assigned worker ID")
    q: Optional[str] = Field(default="", description="Omni-search query text")

class TargetNumberItem(BaseModel):
    id: int
    phone: str
    password_hint: Optional[str] = ""
    operator: Optional[str] = ""
    circle: Optional[str] = ""
    pool_type: Optional[str] = "new"
    country: Optional[str] = "IN"

class DispatchResponse(BaseModel):
    success: bool
    found: Optional[bool] = None
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None
