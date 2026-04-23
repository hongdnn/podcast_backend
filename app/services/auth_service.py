"""
Local authentication service using the app users table.
"""
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings
from app.models.schemas import AuthResponse, UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self._validate_service_role_key()
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=ClientOptions(
                postgrest_client_timeout=settings.supabase_postgrest_timeout,
                storage_client_timeout=settings.supabase_storage_timeout,
            ),
        )

    def _jwt_role(self, token: str) -> Optional[str]:
        try:
            payload = token.split(".")[1]
            padded_payload = payload + "=" * (-len(payload) % 4)
            decoded_payload = base64.urlsafe_b64decode(padded_payload)
            return json.loads(decoded_payload).get("role")
        except (IndexError, ValueError, json.JSONDecodeError):
            return None

    def _validate_service_role_key(self) -> None:
        service_role = self._jwt_role(settings.supabase_service_role_key)
        if settings.supabase_service_role_key == settings.supabase_anon_key or service_role != "service_role":
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY must be the Supabase service_role key, not the anon key. "
                "Copy it from Supabase Dashboard > Project Settings > API > service_role key."
            )

    def _hash_password(self, password: str) -> str:
        self._validate_password_length(password)
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        self._validate_password_length(plain_password)
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )

    def _validate_password_length(self, password: str) -> None:
        if len(password.encode("utf-8")) > 72:
            raise Exception("Password must be 72 bytes or fewer")

    def _create_token(self, user_id: str, expires_delta: timedelta, token_type: str) -> str:
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": user_id,
            "type": token_type,
            "exp": expire
        }
        return jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

    def _create_access_token(self, user_id: str) -> str:
        return self._create_token(
            user_id=user_id,
            expires_delta=timedelta(days=settings.jwt_expire_days),
            token_type="access"
        )

    def _create_refresh_token(self, user_id: str) -> str:
        return self._create_token(
            user_id=user_id,
            expires_delta=timedelta(days=settings.jwt_refresh_expire_days),
            token_type="refresh"
        )

    def _build_auth_response(self, user_record: dict) -> AuthResponse:
        user_response = self._build_user_response(user_record)
        return AuthResponse(
            user=user_response,
            access_token=self._create_access_token(user_response.id),
            refresh_token=self._create_refresh_token(user_response.id)
        )

    def _build_user_response(self, user_record: dict) -> UserResponse:
        return UserResponse(
            id=user_record["id"],
            name=user_record["name"],
            email=user_record["email"],
            preferences=user_record.get("preferences", ""),
            daily_delivery_time=user_record.get("daily_delivery_time"),
            timezone=user_record.get("timezone"),
            created_at=datetime.fromisoformat(user_record["created_at"].replace("Z", "+00:00"))
        )

    def _get_user_id_from_token(self, token: str) -> str:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )
            user_id: Optional[str] = payload.get("sub")
            token_type: Optional[str] = payload.get("type")
            if not user_id:
                raise Exception("Invalid token: missing subject")
            if token_type != "access":
                raise Exception("Invalid token: use access_token, not refresh_token")
            return user_id
        except ExpiredSignatureError as e:
            raise Exception("Invalid token: access token expired") from e
        except JWTError as e:
            raise Exception(f"Invalid token: {str(e)}") from e

    def get_user_id_from_access_token(self, token: str) -> str:
        """Validate an app access token locally and return its user id."""
        return self._get_user_id_from_token(token)

    async def signup(
        self,
        email: str,
        password: str,
        name: str,
        preferences: str,
        daily_delivery_time: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> AuthResponse:
        """Create a local user and return app JWTs."""
        try:
            existing_user = self.supabase.table("users").select("id").eq("email", email).execute()
            if existing_user.data:
                raise Exception("Email already registered")

            user_data = {
                "email": email,
                "password": self._hash_password(password),
                "name": name,
                "preferences": preferences,
                "daily_delivery_time": daily_delivery_time,
                "timezone": timezone
            }
            result = self.supabase.table("users").insert(user_data).execute()
            if not result.data:
                raise Exception("Failed to create user")

            return self._build_auth_response(result.data[0])

        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise Exception(f"Signup failed: {str(e)}")

    async def login(self, email: str, password: str) -> AuthResponse:
        """Authenticate a local user and return app JWTs."""
        try:
            result = self.supabase.table("users").select("*").eq("email", email).execute()
            if not result.data:
                raise Exception("Invalid credentials")

            user_record = result.data[0]
            hashed_password = user_record.get("password")
            if not hashed_password or not self._verify_password(password, hashed_password):
                raise Exception("Invalid credentials")

            return self._build_auth_response(user_record)

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise Exception(f"Login failed: {str(e)}")

    async def get_current_user(self, token: str) -> UserResponse:
        """Get current user from an app JWT."""
        try:
            user_id = self._get_user_id_from_token(token)
            result = self.supabase.table("users").select("*").eq("id", user_id).execute()

            if not result.data:
                raise Exception("User data not found")

            return self._build_user_response(result.data[0])

        except Exception as e:
            logger.error(f"Get current user error: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")

    async def update_preferences(self, token: str, preferences: str) -> UserResponse:
        """Update user preferences."""
        try:
            user = await self.get_current_user(token)
            result = self.supabase.table("users").update({
                "preferences": preferences,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user.id).execute()

            if not result.data:
                raise Exception("Failed to update preferences")

            return self._build_user_response(result.data[0])

        except Exception as e:
            logger.error(f"Update preferences error: {str(e)}")
            raise Exception(f"Failed to update preferences: {str(e)}")
