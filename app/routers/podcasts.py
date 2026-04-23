"""
Podcast router for podcast generation and management
"""

import asyncio
import json
import logging
import uuid
from typing import Dict

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    PodcastGenerateRequest,
    PodcastStatusResponse,
    PodcastResponse,
    PodcastHistoryResponse,
    PodcastStatus,
)
from app.services.auth_service import AuthService
from app.services.podcast_service import PodcastService

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Initialize services
auth_service = AuthService()
podcast_service = PodcastService()


@router.post("/generate", response_model=Dict)
async def generate_podcast(
    request: PodcastGenerateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Generate a new podcast."""
    try:
        user_id = auth_service.get_user_id_from_access_token(credentials.credentials)

        task_id = str(uuid.uuid4())
        await podcast_service.register_task(task_id, user_id)
        logger.info(
            "Registered task %s with payload from frontend: user_id=%s payload=%s",
            task_id,
            user_id,
            request.model_dump(),
        )

        await podcast_service.enqueue_generation(
            task_id=task_id,
            user_id=user_id,
            topic=request.topics,
            duration=request.duration,
            voice_preference=request.voice_preference,
        )

        return {"task_id": task_id, "status": PodcastStatus.PROCESSING.value}

    except Exception as e:
        logger.error(f"Generate podcast error: {str(e)}")
        status_code = (
            status.HTTP_401_UNAUTHORIZED
            if "authentication failed" in str(e).lower()
            or "invalid token" in str(e).lower()
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=str(e))


@router.get("/events/{task_id}")
async def stream_podcast_events(task_id: str):
    """Stream podcast generation events for a task using Server-Sent Events."""
    try:
        task_info = podcast_service.task_status.get(task_id)
        if not task_info:
            raise Exception("Task not found")

        async def event_generator():
            current_status = podcast_service.task_status.get(task_id)
            if current_status and current_status.get("status") in (
                PodcastStatus.COMPLETED,
                PodcastStatus.FAILED,
            ):
                event_name = (
                    "completed"
                    if current_status["status"] == PodcastStatus.COMPLETED
                    else "failed"
                )
                event_data = (
                    current_status.get("podcast")
                    if event_name == "completed"
                    else current_status
                )
                yield f"event: {event_name}\n"
                yield f"data: {json.dumps(event_data, default=str)}\n\n"
                return

            queue = podcast_service.get_task_queue(task_id)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {event['event']}\n"
                    yield f"data: {json.dumps(event['data'], default=str)}\n\n"
                    if event["event"] in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield "event: ping\n"
                    yield 'data: {"status": "processing"}\n\n'

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    except Exception as e:
        logger.error(f"Stream podcast events error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )


@router.get("/status/{task_id}", response_model=PodcastStatusResponse)
async def get_podcast_status(
    task_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get podcast generation status"""
    try:
        user_id = auth_service.get_user_id_from_access_token(credentials.credentials)
        task_info = podcast_service.task_status.get(task_id)
        if task_info and task_info.get("user_id") != user_id:
            raise Exception("Task not found")

        # Get status
        status_info = await podcast_service.get_generation_status(task_id)
        return status_info

    except Exception as e:
        logger.error(f"Get podcast status error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )


@router.get("/history", response_model=PodcastHistoryResponse)
async def get_podcast_history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    limit: int = 10,
    offset: int = 0,
):
    """Get user's podcast history"""
    try:
        user_id = auth_service.get_user_id_from_access_token(credentials.credentials)

        # Get history
        history = await podcast_service.get_list_podcasts(
            user_id=user_id, limit=limit, offset=offset
        )
        return history

    except Exception as e:
        logger.error(f"Get podcast history error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{podcast_id}", response_model=PodcastResponse)
async def get_podcast(
    podcast_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get specific podcast details"""
    try:
        user_id = auth_service.get_user_id_from_access_token(credentials.credentials)

        # Get podcast
        podcast = await podcast_service.get_podcast(podcast_id, user_id)
        return podcast

    except Exception as e:
        logger.error(f"Get podcast error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Podcast not found"
        )
