from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from uuid import UUID
from api.schemas import AgentRunResponse
from api.routes.sites import get_current_user
from db import db_client

router = APIRouter(prefix="/runs", tags=["Agent Runs"])

@router.get("", response_model=List[AgentRunResponse])
async def list_runs(
    site_id: Optional[UUID] = Query(None, description="Filter runs by site ID"),
    limit: int = Query(50, ge=1, le=100, description="Max number of runs to return"),
    user_id: str = Depends(get_current_user)
):
    site_id_str = str(site_id) if site_id else None
    runs = db_client.get_recent_runs(site_id=site_id_str, limit=limit)
    return runs
