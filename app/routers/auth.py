"""
Authentication router for user signup, login, and profile management
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.models.schemas import (
    UserSignup, UserLogin, AuthResponse, UserResponse, PreferencesUpdate
)
from app.services.auth_service import AuthService
from app.core.config import settings

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Initialize auth service
auth_service = AuthService()

@router.post("/signup", response_model=AuthResponse)
async def signup(user_data: UserSignup):
    """Register a new user"""
    try:
        result = await auth_service.signup(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
            preferences=user_data.preferences
        )
        return result
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=AuthResponse)
async def login(user_data: UserLogin):
    """Authenticate user and return tokens"""
    try:
        result = await auth_service.login(
            email=user_data.email,
            password=user_data.password
        )
        return result
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user profile"""
    try:
        user = await auth_service.get_current_user(credentials.credentials)
        return user
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

@router.put("/preferences", response_model=UserResponse)
async def update_preferences(
    preferences_data: PreferencesUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update user preferences"""
    try:
        user = await auth_service.update_preferences(
            token=credentials.credentials,
            preferences=preferences_data.preferences
        )
        return user
    except Exception as e:
        logger.error(f"Update preferences error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )