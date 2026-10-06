from fastapi import APIRouter, Depends, HTTPException, Header, status
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from api.schemas import SiteCreate, SiteUpdate, SiteResponse
from db import db_client
from orchestrator import run_orchestrator
from loguru import logger
import os

router = APIRouter(prefix="/sites", tags=["Sites"])

# Authentication dependency
async def get_current_user(authorization: Optional[str] = Header(None)):
    # If mock mode is enabled, bypass authentication
    if os.getenv("MOCK_SUPABASE", "true").lower() == "true":
        return "00000000-0000-0000-0000-000000000000"
        
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
        
    try:
        token = authorization.replace("Bearer ", "")
        # Call Supabase to verify token and get user
        user = db_client.client.auth.get_user(token)
        return user.user.id
    except Exception as e:
        logger.error(f"JWT Verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token or expired session"
        )

class TriggerPayload(BaseModel):
    site_id: Optional[str] = None

@router.get("", response_model=List[SiteResponse])
async def list_sites(user_id: str = Depends(get_current_user)):
    sites = db_client.get_all_sites()
    # Filter by user if not mock/admin, or return all
    return sites

@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site(site: SiteCreate, user_id: str = Depends(get_current_user)):
    try:
        site_dict = site.model_dump()
        # Convert HttpUrl to string
        site_dict["url"] = str(site_dict["url"])
        site_dict["user_id"] = user_id
        
        new_site = db_client.add_site(site_dict)
        return new_site
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create site: {e}"
        )

@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(site_id: UUID, site_update: SiteUpdate, user_id: str = Depends(get_current_user)):
    existing = db_client.get_site(str(site_id))
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        
    try:
        update_dict = site_update.model_dump(exclude_unset=True)
        if "url" in update_dict and update_dict["url"] is not None:
            update_dict["url"] = str(update_dict["url"])
            
        updated = db_client.update_site(str(site_id), update_dict)
        return updated
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update site: {e}"
        )

@router.delete("/{site_id}", status_code=status.HTTP_200_OK)
async def delete_site(site_id: UUID, user_id: str = Depends(get_current_user)):
    success = db_client.delete_site(str(site_id))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return {"detail": "Site successfully deleted"}

# Register the trigger route under router as well
@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(payload: Optional[TriggerPayload] = None, user_id: str = Depends(get_current_user)):
    """
    Manually trigger the orchestrator for a specific site or all active sites.
    """
    site_id = payload.site_id if payload else None
    
    if site_id:
        site = db_client.get_site(site_id)
        if not site:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        if not site.get("is_active", True):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Site is inactive")
        
        logger.info(f"Manual execution triggered for site ID: {site_id}")
        # Run orchestrator graph for this specific site
        # Since it runs async, we can await it or run in background.
        # Awaiting is fine for HTTP response validation in test cases.
        await run_orchestrator(sites=[site])
        return {"detail": f"Orchestrator successfully run for site: {site['name']}"}
    else:
        logger.info("Manual execution triggered for ALL active sites")
        await run_orchestrator()
        return {"detail": "Orchestrator successfully run for all active sites"}
