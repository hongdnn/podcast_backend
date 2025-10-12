"""
Main podcast service that orchestrates the entire podcast generation process
"""
import logging
from typing import Optional, Dict, Any
import uuid
from datetime import datetime
import asyncio
from supabase import create_client, Client

from app.core.config import settings
from app.models.schemas import (
    PodcastStatusResponse, PodcastResponse, PodcastHistoryResponse,
    PodcastStatus, GenerationStep
)
from app.services.google_ai_service import GoogleAIService
from app.services.elevenlabs_service import ElevenLabsService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

class PodcastService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
        self.google_ai_service = GoogleAIService()
        self.tts_service = ElevenLabsService()
        self.storage_service = StorageService()
        
        # In-memory task tracking (in production, use Redis or database)
        self.task_status: Dict[str, Dict[str, Any]] = {}
    
    async def generate_podcast(
        self,
        task_id: str,
        user_id: str,
        topic: Optional[str] = None,
        duration: int = 5,
        user_preferences: str = "technology"
    ):
        """Generate a complete podcast (runs in background)"""
        try:
            # Initialize task status
            # self.task_status[task_id] = {
            #     "status": PodcastStatus.PROCESSING,
            #     "progress": 0,
            #     "current_step": GenerationStep.FETCHING_NEWS,
            #     "error_message": None
            # }
            
            # Use topic or user preferences
            search_topic = topic or user_preferences
            
            # Create podcast record in database
            # podcast_data = {
            #     "id": str(uuid.uuid4()),
            #     "user_id": user_id,
            #     "title": f"AI Podcast: {search_topic.title()}",
            #     "topic": search_topic,
            #     "status": PodcastStatus.PROCESSING.value,
            #     "duration_seconds": 0
            # }
            
            # result = self.supabase.table("podcasts").insert(podcast_data).execute()
            # podcast_id = result.data[0]["id"]
            
            # # Log generation start
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.FETCHING_NEWS.value, 
            #     "started", 
            #     f"Starting podcast generation for topic: {search_topic}"
            # )
            
            # Step 1: Fetch latest news (20% progress)
            # self._update_task_status(task_id, 20, GenerationStep.FETCHING_NEWS)
            news_data = await self.google_ai_service.search_latest_news(search_topic)
            
    
            
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.FETCHING_NEWS.value, 
            #     "completed", 
            #     f"Found {len(news_data)} news articles"
            # )
            
            # Step 2: Generate script (50% progress)
            self._update_task_status(task_id, 50, GenerationStep.GENERATING_SCRIPT)
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.GENERATING_SCRIPT.value, 
            #     "started", 
            #     "Generating podcast script"
            # )
            
            script = await self.google_ai_service.generate_podcast_script(
                news_data, search_topic, duration
            )
            print("📝 Generated Script Successfully:\n", script)
            # Enhance script for TTS
            # enhanced_script = await self.google_ai_service.enhance_script_for_audio(script)
            
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.GENERATING_SCRIPT.value, 
            #     "completed", 
            #     f"Generated script of {len(enhanced_script)} characters"
            # )
            
            # # Step 3: Generate audio (80% progress)
            # self._update_task_status(task_id, 80, GenerationStep.GENERATING_AUDIO)
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.GENERATING_AUDIO.value, 
            #     "started", 
            #     "Converting script to audio"
            # )
            
            # audio_data = await self.tts_service.generate_podcast_audio(enhanced_script)
            
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.GENERATING_AUDIO.value, 
            #     "completed", 
            #     f"Generated audio of {len(audio_data)} bytes"
            # )
            
            # # Step 4: Upload audio (95% progress)
            # self._update_task_status(task_id, 95, GenerationStep.UPLOADING_AUDIO)
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.UPLOADING_AUDIO.value, 
            #     "started", 
            #     "Uploading audio to storage"
            # )
            
            # filename = f"podcast_{podcast_id}.mp3"
            # audio_url, storage_provider = await self.storage_service.upload_audio_file(
            #     audio_data, filename
            # )
            
            # await self._log_generation_step(
            #     podcast_id, 
            #     GenerationStep.UPLOADING_AUDIO.value, 
            #     "completed", 
            #     f"Audio uploaded to {storage_provider}: {audio_url}"
            # )
            
            # # Update podcast record with results
            # estimated_duration = len(enhanced_script.split()) * 0.5  # Rough estimate
            
            # update_data = {
            #     "script": enhanced_script,
            #     "audio_url": audio_url,
            #     "status": PodcastStatus.COMPLETED.value,
            #     "duration_seconds": int(estimated_duration),
            #     "completed_at": datetime.utcnow().isoformat()
            # }
            
            # self.supabase.table("podcasts").update(update_data).eq("id", podcast_id).execute()
            
            # # Complete task (100% progress)
            # self.task_status[task_id] = {
            #     "status": PodcastStatus.COMPLETED,
            #     "progress": 100,
            #     "current_step": None,
            #     "audio_url": audio_url,
            #     "error_message": None
            # }
            
            # logger.info(f"Podcast generation completed for task: {task_id}")
            return script
            
        except Exception as e:
            logger.error(f"Podcast generation failed for task {task_id}: {str(e)}")
            
            # Update task status with error
            self.task_status[task_id] = {
                "status": PodcastStatus.FAILED,
                "progress": 0,
                "current_step": None,
                "audio_url": None,
                "error_message": str(e)
            }
            
            # Update database record
            try:
                self.supabase.table("podcasts").update({
                    "status": PodcastStatus.FAILED.value
                }).eq("id", podcast_id).execute()
                
                await self._log_generation_step(
                    podcast_id, 
                    "error", 
                    "failed", 
                    f"Generation failed: {str(e)}"
                )
            except:
                pass  # Don't fail if logging fails
    
    def _update_task_status(self, task_id: str, progress: int, step: GenerationStep):
        """Update task status in memory"""
        if task_id in self.task_status:
            self.task_status[task_id].update({
                "progress": progress,
                "current_step": step
            })
    
    async def _log_generation_step(self, podcast_id: str, step: str, status: str, details: str):
        """Log generation step to database"""
        try:
            log_data = {
                "podcast_id": podcast_id,
                "step": step,
                "status": status,
                "details": details
            }
            self.supabase.table("generation_logs").insert(log_data).execute()
        except Exception as e:
            logger.error(f"Failed to log generation step: {str(e)}")
    
    async def get_generation_status(self, task_id: str) -> PodcastStatusResponse:
        """Get podcast generation status"""
        if task_id not in self.task_status:
            raise Exception("Task not found")
        
        status_data = self.task_status[task_id]
        
        return PodcastStatusResponse(
            task_id=task_id,
            status=status_data["status"],
            progress=status_data["progress"],
            current_step=status_data.get("current_step"),
            audio_url=status_data.get("audio_url"),
            error_message=status_data.get("error_message")
        )
    
    async def get_user_podcasts(self, user_id: str, limit: int = 10, offset: int = 0) -> PodcastHistoryResponse:
        """Get user's podcast history"""
        try:
            result = self.supabase.table("podcasts").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            podcasts = []
            for record in result.data:
                podcast = PodcastResponse(
                    id=record["id"],
                    user_id=record["user_id"],
                    title=record["title"],
                    topic=record.get("topic"),
                    script=record.get("script"),
                    audio_url=record.get("audio_url"),
                    status=PodcastStatus(record["status"]),
                    duration_seconds=record.get("duration_seconds", 0),
                    created_at=datetime.fromisoformat(record["created_at"].replace('Z', '+00:00')),
                    completed_at=datetime.fromisoformat(record["completed_at"].replace('Z', '+00:00')) if record.get("completed_at") else None
                )
                podcasts.append(podcast)
            
            # Get total count
            count_result = self.supabase.table("podcasts").select("id", count="exact").eq("user_id", user_id).execute()
            total = count_result.count or 0
            
            return PodcastHistoryResponse(
                podcasts=podcasts,
                total=total
            )
            
        except Exception as e:
            logger.error(f"Get user podcasts error: {str(e)}")
            raise Exception(f"Failed to get podcasts: {str(e)}")
    
    async def get_podcast(self, podcast_id: str, user_id: str) -> PodcastResponse:
        """Get specific podcast details"""
        try:
            result = self.supabase.table("podcasts").select("*").eq(
                "id", podcast_id
            ).eq("user_id", user_id).execute()
            
            if not result.data:
                raise Exception("Podcast not found")
            
            record = result.data[0]
            
            return PodcastResponse(
                id=record["id"],
                user_id=record["user_id"],
                title=record["title"],
                topic=record.get("topic"),
                script=record.get("script"),
                audio_url=record.get("audio_url"),
                status=PodcastStatus(record["status"]),
                duration_seconds=record.get("duration_seconds", 0),
                created_at=datetime.fromisoformat(record["created_at"].replace('Z', '+00:00')),
                completed_at=datetime.fromisoformat(record["completed_at"].replace('Z', '+00:00')) if record.get("completed_at") else None
            )
            
        except Exception as e:
            logger.error(f"Get podcast error: {str(e)}")
            raise Exception(f"Failed to get podcast: {str(e)}")