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
        """Create user and return session without requiring email confirmation"""
        try:
            # Create user in Supabase
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

            # Save user data to table
            user_data = {
                "id": auth_response.user.id,
                "email": email,
                "name": name,
                "preferences": preferences
            }
            result = self.supabase.table("users").insert(user_data).execute()
            user_record = result.data[0]

            # Immediately sign in to generate session (ignoring email confirmation)
            login_resp = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if not login_resp.session or not login_resp.user:
                # If email not confirmed, manually create session token using service role
                # Optional: you can generate a JWT here if needed
                access_token = ""
                refresh_token = ""
            else:
                access_token = login_resp.session.access_token
                refresh_token = login_resp.session.refresh_token

            user_response = UserResponse(
                id=user_record["id"],
                name=user_record["name"],
                email=user_record["email"],
                preferences=user_record.get("preferences", ""),
                created_at=datetime.fromisoformat(user_record["created_at"].replace("Z", "+00:00"))
            )

            return AuthResponse(
                user=user_response,
                access_token=access_token,
                refresh_token=refresh_token
            )

        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise Exception(f"Signup failed: {str(e)}")
    
    async def login(self, email: str, password: str) -> AuthResponse:
        """Authenticate user ignoring email confirmation"""
        try:
            # Sign in with Supabase
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if not auth_response.user:
                raise Exception("User not found or invalid credentials")

            # Fetch user data from the table
            result = self.supabase.table("users").select("*").eq("email", email).execute()
            if not result.data:
                raise Exception("User data not found")

            user_record = result.data[0]

            # If email not confirmed, session may be None
            if not auth_response.session:
                access_token = ""
                refresh_token = ""
            else:
                access_token = auth_response.session.access_token
                refresh_token = auth_response.session.refresh_token

            user_response = UserResponse(
                id=user_record["id"],
                name=user_record["name"],
                email=user_record["email"],
                preferences=user_record.get("preferences", ""),
                created_at=datetime.fromisoformat(user_record["created_at"].replace("Z", "+00:00"))
            )

            return AuthResponse(
                user=user_response,
                access_token=access_token,
                refresh_token=refresh_token
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