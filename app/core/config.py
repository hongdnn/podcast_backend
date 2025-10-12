"""
Configuration settings for the AI Podcast Generator
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    app_name: str = "AI Podcast Generator"
    debug: bool = False
    
    # Supabase settings
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    
    # Google AI settings
    google_api_key: str
    
    # ElevenLabs settings
    elevenlabs_api_key: str
    
    # Firebase settings (fallback storage)
    firebase_credentials_path: Optional[str] = None
    firebase_storage_bucket: Optional[str] = None
    
    # Database settings
    database_url: Optional[str] = None
    
    # JWT settings
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()