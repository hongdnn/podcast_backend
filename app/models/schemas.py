"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

class PodcastStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class GenerationStep(str, Enum):
    FETCHING_NEWS = "fetching_news"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_AUDIO = "generating_audio"
    UPLOADING_AUDIO = "uploading_audio"

# Auth schemas
class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    preferences: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    preferences: str
    created_at: datetime

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str

class PreferencesUpdate(BaseModel):
    preferences: str

# Podcast schemas
class PodcastGenerateRequest(BaseModel):
    topic: Optional[str] = None
    duration: Optional[int] = 5  # minutes

class PodcastGenerateResponse(BaseModel):
    task_id: str
    status: PodcastStatus
    estimated_time: int  # seconds

class PodcastStatusResponse(BaseModel):
    task_id: str
    status: PodcastStatus
    progress: int  # 0-100
    current_step: Optional[GenerationStep] = None
    audio_url: Optional[str] = None
    error_message: Optional[str] = None

class PodcastResponse(BaseModel):
    id: str
    user_id: str
    title: str
    topic: Optional[str]
    script: Optional[str]
    audio_url: Optional[str]
    status: PodcastStatus
    duration_seconds: int
    created_at: datetime
    completed_at: Optional[datetime]

class PodcastHistoryResponse(BaseModel):
    podcasts: List[PodcastResponse]
    total: int

# Generation log schema
class GenerationLog(BaseModel):
    id: str
    podcast_id: str
    step: str
    status: str
    details: Optional[str]
    created_at: datetime