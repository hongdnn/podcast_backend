"""
Podcast router for podcast generation and management
"""
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
import uuid

from app.models.schemas import (
    PodcastGenerateRequest, PodcastGenerateResponse, PodcastStatusResponse,
    PodcastResponse, PodcastHistoryResponse
)
from app.services.auth_service import AuthService
from app.services.podcast_service import PodcastService

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Initialize services
auth_service = AuthService()
podcast_service = PodcastService()

@router.post("/generate", response_model=PodcastGenerateResponse)
async def generate_podcast(
    request: PodcastGenerateRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Generate a new podcast"""
    try:
        # Get current user
        user = await auth_service.get_current_user(credentials.credentials)
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Start podcast generation in background
        background_tasks.add_task(
            podcast_service.generate_podcast,
            task_id=task_id,
            user_id=user.id,
            topic=request.topic,
            duration=request.duration,
            user_preferences=user.preferences
        )
        
        return PodcastGenerateResponse(
            task_id=task_id,
            status="processing",
            estimated_time=300  # 5 minutes estimate
        )
        
    except Exception as e:
        logger.error(f"Generate podcast error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/status/{task_id}", response_model=PodcastStatusResponse)
async def get_podcast_status(
    task_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get podcast generation status"""
    try:
        # Verify user authentication
        await auth_service.get_current_user(credentials.credentials)
        
        # Get status
        status_info = await podcast_service.get_generation_status(task_id)
        return status_info
        
    except Exception as e:
        logger.error(f"Get podcast status error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

@router.get("/history", response_model=PodcastHistoryResponse)
async def get_podcast_history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    limit: int = 10,
    offset: int = 0
):
    """Get user's podcast history"""
    try:
        # Get current user
        user = await auth_service.get_current_user(credentials.credentials)
        
        # Get history
        history = await podcast_service.get_user_podcasts(
            user_id=user.id,
            limit=limit,
            offset=offset
        )
        return history
        
    except Exception as e:
        logger.error(f"Get podcast history error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{podcast_id}", response_model=PodcastResponse)
async def get_podcast(
    podcast_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get specific podcast details"""
    try:
        # Get current user
        user = await auth_service.get_current_user(credentials.credentials)
        
        # Get podcast
        podcast = await podcast_service.get_podcast(podcast_id, user.id)
        return podcast
        
    except Exception as e:
        logger.error(f"Get podcast error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast not found"
        )