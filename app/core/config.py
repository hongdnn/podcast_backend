"""
Configuration settings for the AI Podcast Generator
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    app_name: str = "AI Podcast Generator"
    debug: bool = False
    
    # Supabase settings
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_postgrest_timeout: int = 30
    supabase_storage_timeout: int = 60
    
    # Google AI settings
    google_api_key: str
    google_search_api_key: str 
    search_engine_id: str

    # Vertex AI Search settings
    vertex_project_id: Optional[str] = None
    vertex_search_location: str = "global"
    vertex_search_serving_config: str = "default_search"
    vertex_search_filter: Optional[str] = None
    
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
    jwt_expire_days: int = 1
    jwt_refresh_expire_days: int = 7
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
