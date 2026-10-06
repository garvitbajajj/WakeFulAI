from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from api.schemas import AnomalyResponse
from api.routes.sites import get_current_user, owned_site_ids
from db import db_client

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])

@router.get("", response_model=List[AnomalyResponse])
async def list_unresolved_anomalies(user_id: str = Depends(get_current_user)):
    anomalies = db_client.get_unresolved_anomalies(site_ids=owned_site_ids(user_id))
    return anomalies

@router.post("/{anomaly_id}/resolve", response_model=AnomalyResponse)
async def resolve_anomaly(anomaly_id: UUID, user_id: str = Depends(get_current_user)):
    anomaly = db_client.resolve_anomaly(str(anomaly_id), site_ids=owned_site_ids(user_id))
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly not found"
        )
    return anomaly
