from fastapi import APIRouter, Depends, HTTPException, Header, status
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from api.schemas import SiteCreate, SiteUpdate, SiteResponse
from db import db_client
from orchestrator import run_orchestrator
from loguru import logger

router = APIRouter(prefix="/sites", tags=["Sites"])

# Authentication dependency
async def get_current_user(authorization: Optional[str] = Header(None)):
    # If mock mode is enabled, bypass authentication
    if db_client.mock_mode:
        # Local single-user mode: no owner filtering
        return None
        
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

def get_owned_site(site_id: str, user_id: Optional[str]) -> dict:
    """Fetch a site, 404-ing if it doesn't exist or belongs to another user."""
    site = db_client.get_site(site_id)
    if not site or (user_id and site.get("user_id") != user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site

def owned_site_ids(user_id: Optional[str]) -> Optional[list[str]]:
    """IDs of the user's sites, or None (no filter) in local single-user mode."""
    return None if user_id is None else [s["id"] for s in db_client.get_all_sites(user_id)]

class TriggerPayload(BaseModel):
    site_id: Optional[str] = None

@router.get("", response_model=List[SiteResponse])
async def list_sites(user_id: str = Depends(get_current_user)):
    return db_client.get_all_sites(user_id)

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
    get_owned_site(str(site_id), user_id)

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
    get_owned_site(str(site_id), user_id)
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
        site = get_owned_site(site_id, user_id)
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
        if user_id is None:
            await run_orchestrator()
        else:
            # An empty list would make the orchestrator fetch every user's sites, so bail out early
            sites = [s for s in db_client.get_all_sites(user_id) if s.get("is_active", True)]
            if sites:
                await run_orchestrator(sites=sites)
        return {"detail": "Orchestrator successfully run for all active sites"}
