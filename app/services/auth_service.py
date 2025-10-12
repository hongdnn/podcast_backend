"""
Authentication service using Supabase
"""
import logging
from typing import Optional
from datetime import datetime
from supabase import create_client, Client
import jwt

from app.core.config import settings
from app.models.schemas import UserResponse, AuthResponse

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
    
    async def signup(self, email: str, password: str, name: str, preferences: str) -> AuthResponse:
        """Register a new user"""
        try:
            # Sign up user with Supabase Auth
            auth_response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "preferences": preferences
                    }
                }
            })
            
            if not auth_response.user:
                raise Exception("Failed to create user")
            
            # Insert user data into users table
            user_data = {
                "id": auth_response.user.id,
                "email": email,
                "name": name,
                "preferences": preferences
            }
            
            result = self.supabase.table("users").insert(user_data).execute()
            
            if not result.data:
                raise Exception("Failed to save user data")
            
            user_record = result.data[0]
            
            # Create response
            user_response = UserResponse(
                id=user_record["id"],
                name=user_record["name"],
                email=user_record["email"],
                preferences=user_record["preferences"],
                created_at=datetime.fromisoformat(user_record["created_at"].replace('Z', '+00:00'))
            )
            
            return AuthResponse(
                user=user_response,
                access_token=auth_response.session.access_token if auth_response.session else "",
                refresh_token=auth_response.session.refresh_token if auth_response.session else ""
            )
            
        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise Exception(f"Signup failed: {str(e)}")
    
    async def login(self, email: str, password: str) -> AuthResponse:
        """Authenticate user"""
        try:
            # Sign in with Supabase Auth
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user or not auth_response.session:
                raise Exception("Invalid credentials")
            
            # Get user data from users table
            result = self.supabase.table("users").select("*").eq("id", auth_response.user.id).execute()
            
            if not result.data:
                raise Exception("User data not found")
            
            user_record = result.data[0]
            
            # Create response
            user_response = UserResponse(
                id=user_record["id"],
                name=user_record["name"],
                email=user_record["email"],
                preferences=user_record["preferences"],
                created_at=datetime.fromisoformat(user_record["created_at"].replace('Z', '+00:00'))
            )
            
            return AuthResponse(
                user=user_response,
                access_token=auth_response.session.access_token,
                refresh_token=auth_response.session.refresh_token
            )
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise Exception(f"Login failed: {str(e)}")
    
    async def get_current_user(self, token: str) -> UserResponse:
        """Get current user from token"""
        try:
            # Verify token with Supabase
            user_response = self.supabase.auth.get_user(token)
            
            if not user_response.user:
                raise Exception("Invalid token")
            
            # Get user data from users table
            result = self.supabase.table("users").select("*").eq("id", user_response.user.id).execute()
            
            if not result.data:
                raise Exception("User data not found")
            
            user_record = result.data[0]
            
            return UserResponse(
                id=user_record["id"],
                name=user_record["name"],
                email=user_record["email"],
                preferences=user_record["preferences"],
                created_at=datetime.fromisoformat(user_record["created_at"].replace('Z', '+00:00'))
            )
            
        except Exception as e:
            logger.error(f"Get current user error: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")
    
    async def update_preferences(self, token: str, preferences: str) -> UserResponse:
        """Update user preferences"""
        try:
            # Get current user
            user = await self.get_current_user(token)
            
            # Update preferences in users table
            result = self.supabase.table("users").update({
                "preferences": preferences,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user.id).execute()
            
            if not result.data:
                raise Exception("Failed to update preferences")
            
            user_record = result.data[0]
            
            return UserResponse(
                id=user_record["id"],
                name=user_record["name"],
                email=user_record["email"],
                preferences=user_record["preferences"],
                created_at=datetime.fromisoformat(user_record["created_at"].replace('Z', '+00:00'))
            )
            
        except Exception as e:
            logger.error(f"Update preferences error: {str(e)}")
            raise Exception(f"Failed to update preferences: {str(e)}")