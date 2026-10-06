from pydantic import BaseModel, ConfigDict, HttpUrl, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# --- Target Sites Schemas ---

class SiteBase(BaseModel):
    url: HttpUrl
    name: str = Field(..., min_length=1, max_length=100)
    session_flow: Optional[str] = None
    check_interval_minutes: Optional[int] = Field(default=10, ge=1)
    is_active: Optional[bool] = True

class SiteCreate(SiteBase):
    pass

class SiteUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    name: Optional[str] = None
    session_flow: Optional[str] = None
    check_interval_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

class SiteResponse(SiteBase):
    id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Agent Runs Schemas ---

class AgentRunResponse(BaseModel):
    id: UUID
    site_id: UUID
    agent_type: str
    status: str
    latency_ms: Optional[int] = None
    screenshot_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Anomalies Schemas ---

class AnomalyResponse(BaseModel):
    id: UUID
    site_id: UUID
    detected_at: datetime
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    resolved: bool

    model_config = ConfigDict(from_attributes=True)
