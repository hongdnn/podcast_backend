"""
Storage service with Supabase storage and Firebase fallback
"""
import logging
from typing import Optional, Tuple
import uuid
from datetime import datetime
import io
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import firebase_admin
from firebase_admin import credentials, storage as firebase_storage

from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # Initialize Supabase client
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=ClientOptions(
                postgrest_client_timeout=settings.supabase_postgrest_timeout,
                storage_client_timeout=settings.supabase_storage_timeout,
            ),
        )
        
        # Initialize Firebase (fallback)
        self.firebase_initialized = False
        self._init_firebase()
    
    def _init_firebase(self):
        """Initialize Firebase if credentials are provided"""
        try:
            if settings.firebase_credentials_path and settings.firebase_storage_bucket:
                if not firebase_admin._apps:
                    cred = credentials.Certificate(settings.firebase_credentials_path)
                    firebase_admin.initialize_app(cred, {
                        'storageBucket': settings.firebase_storage_bucket
                    })
                self.firebase_initialized = True
                logger.info("Firebase storage initialized")
        except Exception as e:
            logger.warning(f"Firebase initialization failed: {str(e)}")
            self.firebase_initialized = False
            
    async def upload_audio_file(self, output_file: str) -> Tuple[str, str]:
        """
        Upload local audio file to Supabase storage
        Args:
            output_file: path to local MP3 file
        Returns:
            Tuple[file_url, storage_provider]
        """
        try:
            if not output_file:
                raise Exception("No audio file was generated")

            bucket_name = "podcasts"  # Supabase storage bucket
            filename = output_file.split("/")[-1]
            file_path = f"{filename}"

            # Read local file bytes
            with open(output_file, "rb") as f:
                file_bytes = f.read()

            # Upload to Supabase
            result = self.supabase.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_bytes,
                file_options={
                    "content-type": "audio/mpeg",
                    "cache-control": "3600"
                }
            )

            if result:
                # Get public URL
                public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_path)
                logger.info(f"File uploaded to Supabase: {public_url}")
                return public_url, "supabase"
            else:
                raise Exception("Supabase upload failed")

        except Exception as e:
            logger.error(f"Supabase upload error: {str(e)}")
            raise
    
    # async def upload_audio_file(self, filename: Optional[str] = None) -> Tuple[str, str]:
    #     """
    #     Upload audio file to storage
    #     Returns: (file_url, storage_provider)
    #     """
    #     if not filename:
    #         filename = f"podcast_{uuid.uuid4()}.mp3"
        
    #     # Try Supabase storage first
    #     try:
    #         return await self._upload_to_supabase(audio_data, filename)
    #     except Exception as e:
    #         logger.error(f"Supabase upload failed: {str(e)}")
            
    #         # Fallback to Firebase
    #         if self.firebase_initialized:
    #             try:
    #                 return await self._upload_to_firebase(audio_data, filename)
    #             except Exception as e:
    #                 logger.error(f"Firebase upload failed: {str(e)}")
            
    #         raise Exception("All storage providers failed")
    
    async def _upload_to_supabase(self, audio_data: bytes, filename: str) -> Tuple[str, str]:
        """Upload to Supabase storage"""
        try:
            # Upload to Supabase storage bucket
            bucket_name = "podcasts"  # You may need to create this bucket
            file_path = f"audio/{datetime.now().strftime('%Y/%m/%d')}/{filename}"
            
            # Upload file
            result = self.supabase.storage.from_(bucket_name).upload(
                path=file_path,
                file=audio_data,
                file_options={
                    "content-type": "audio/mpeg",
                    "cache-control": "3600"
                }
            )
            
            if result:
                # Get public URL
                public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_path)
                logger.info(f"File uploaded to Supabase: {public_url}")
                return public_url, "supabase"
            else:
                raise Exception("Upload failed")
                
        except Exception as e:
            logger.error(f"Supabase upload error: {str(e)}")
            raise
    
    async def _upload_to_firebase(self, audio_data: bytes, filename: str) -> Tuple[str, str]:
        """Upload to Firebase storage (fallback)"""
        try:
            bucket = firebase_storage.bucket()
            file_path = f"podcasts/audio/{datetime.now().strftime('%Y/%m/%d')}/{filename}"
            
            # Upload file
            blob = bucket.blob(file_path)
            blob.upload_from_string(
                audio_data,
                content_type="audio/mpeg"
            )
            
            # Make file publicly accessible
            blob.make_public()
            
            public_url = blob.public_url
            logger.info(f"File uploaded to Firebase: {public_url}")
            return public_url, "firebase"
            
        except Exception as e:
            logger.error(f"Firebase upload error: {str(e)}")
            raise
    
    async def delete_file(self, file_url: str, storage_provider: str) -> bool:
        """Delete file from storage"""
        try:
            if storage_provider == "supabase":
                return await self._delete_from_supabase(file_url)
            elif storage_provider == "firebase":
                return await self._delete_from_firebase(file_url)
            else:
                logger.error(f"Unknown storage provider: {storage_provider}")
                return False
                
        except Exception as e:
            logger.error(f"Delete file error: {str(e)}")
            return False
    
    async def _delete_from_supabase(self, file_url: str) -> bool:
        """Delete file from Supabase storage"""
        try:
            # Extract file path from URL
            # This is a simplified implementation
            bucket_name = "podcasts"
            file_path = file_url.split(f"{bucket_name}/")[-1]
            
            result = self.supabase.storage.from_(bucket_name).remove([file_path])
            return bool(result)
            
        except Exception as e:
            logger.error(f"Supabase delete error: {str(e)}")
            return False
    
    async def _delete_from_firebase(self, file_url: str) -> bool:
        """Delete file from Firebase storage"""
        try:
            bucket = firebase_storage.bucket()
            # Extract blob name from URL
            blob_name = file_url.split(f"{settings.firebase_storage_bucket}/")[-1].split("?")[0]
            
            blob = bucket.blob(blob_name)
            blob.delete()
            return True
            
        except Exception as e:
            logger.error(f"Firebase delete error: {str(e)}")
            return False
    
    async def get_file_info(self, file_url: str) -> Optional[dict]:
        """Get file information"""
        try:
            # This is a basic implementation
            # In production, you might want to store file metadata in database
            return {
                "url": file_url,
                "size": None,  # Would need to fetch from storage
                "created_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Get file info error: {str(e)}")
            return None
