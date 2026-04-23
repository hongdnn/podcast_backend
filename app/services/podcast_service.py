"""
Main podcast service that orchestrates podcast generation.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings
from app.models.schemas import (
    GenerationStep,
    PodcastHistoryResponse,
    PodcastResponse,
    PodcastStatus,
    PodcastStatusResponse,
)
from app.services.elevenlabs_service import ElevenLabsService
from app.services.google_ai_service import GoogleAIService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class PodcastService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=ClientOptions(
                postgrest_client_timeout=settings.supabase_postgrest_timeout,
                storage_client_timeout=settings.supabase_storage_timeout,
            ),
        )
        self.google_ai_service = GoogleAIService()
        self.tts_service = ElevenLabsService()
        self.storage_service = StorageService()

        # In-memory queue/status simulation. Use Redis/Kafka/Postgres LISTEN in production.
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.task_status: Dict[str, Dict[str, Any]] = {}
        self.task_events: Dict[str, asyncio.Queue] = {}

    async def _execute_supabase_query(self, query, operation: str):
        """Run blocking Supabase queries off the event loop."""
        try:
            return await asyncio.to_thread(query.execute)
        except Exception as e:
            raise Exception(f"{operation} failed: {str(e)}") from e

    async def start_worker(self):
        if self.worker_task and not self.worker_task.done():
            return

        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Podcast queue worker started")

    async def stop_worker(self):
        if not self.worker_task:
            return

        self.worker_task.cancel()
        try:
            await self.worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Podcast queue worker stopped")

    async def _worker_loop(self):
        while True:
            job = await self.job_queue.get()
            try:
                await self.generate_podcast(**job)
            finally:
                self.job_queue.task_done()

    async def register_task(self, task_id: str, user_id: str):
        self.task_events[task_id] = asyncio.Queue()
        self.task_status[task_id] = {
            "status": PodcastStatus.PENDING,
            "progress": 0,
            "current_step": None,
            "audio_url": None,
            "error_message": None,
            "user_id": user_id,
        }

    async def enqueue_generation(
        self,
        task_id: str,
        user_id: str,
        topic: Optional[str] = None,
        duration: int = 5,
        voice_preference: str = "neutral",
    ):
        await self.job_queue.put(
            {
                "task_id": task_id,
                "user_id": user_id,
                "topic": topic,
                "duration": duration,
                "voice_preference": voice_preference,
            }
        )
        logger.info(f"Podcast generation queued for task: {task_id} with voice preference: {voice_preference}")

    async def generate_podcast(
        self,
        task_id: str,
        user_id: str,
        topic: Optional[str] = None,
        duration: int = 5,
        voice_preference: str = "neutral",
    ) -> Optional[PodcastResponse]:
        """Run podcast generation in the background."""
        try:
            self.task_status[task_id] = {
                "status": PodcastStatus.PROCESSING,
                "progress": 10,
                "current_step": None,
                "audio_url": None,
                "error_message": None,
                "user_id": user_id,
            }

            search_topic = (topic or "technology").strip()
            logger.info(f"Worker processing task {task_id} with voice preference: {voice_preference}")

            self._update_task_status(task_id, 20, GenerationStep.FETCHING_NEWS)
            news_data = await self.google_ai_service.search_latest_news(search_topic)

            self._update_task_status(task_id, 50, GenerationStep.GENERATING_SCRIPT)
            script = await self.google_ai_service.generate_podcast_script(
                news_data, search_topic, duration
            )

            self._update_task_status(task_id, 80, GenerationStep.GENERATING_AUDIO)
            output_file = await self.tts_service.generate_podcast_audio(
                script,
                voice_preference=voice_preference
            )

            self._update_task_status(task_id, 95, GenerationStep.UPLOADING_AUDIO)
            audio_url, storage_provider = await self.storage_service.upload_audio_file(
                output_file
            )

            estimated_duration = int(len(script.split()) * 0.5)
            podcast_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": f"{search_topic[:1].upper()}{search_topic[1:]} Podcast",
                "topic": search_topic,
                "script": script,
                "audio_url": audio_url,
                "status": PodcastStatus.COMPLETED.value,
                "duration_seconds": estimated_duration,
                "completed_at": datetime.utcnow().isoformat(),
            }
            result = await self._execute_supabase_query(
                self.supabase.table("podcasts").insert(podcast_data),
                "Create podcast record",
            )
            if not result.data:
                raise Exception("Failed to create podcast record")

            podcast = self._build_podcast_response(result.data[0])
            self.task_status[task_id] = {
                "status": PodcastStatus.COMPLETED,
                "progress": 100,
                "current_step": None,
                "audio_url": podcast.audio_url,
                "error_message": None,
                "user_id": user_id,
                "podcast": podcast.model_dump(mode="json"),
            }
            await self._publish_task_event(
                task_id, "completed", podcast.model_dump(mode="json")
            )

            logger.info(f"Podcast generation completed for task: {task_id} using {storage_provider}")
            return podcast

        except Exception as e:
            logger.error(f"Podcast generation failed for task {task_id}: {str(e)}")
            self.task_status[task_id] = {
                "status": PodcastStatus.FAILED,
                "progress": 0,
                "current_step": None,
                "audio_url": None,
                "error_message": str(e),
                "user_id": user_id,
            }
            await self._publish_task_event(task_id, "failed", self.task_status[task_id])
            return None

    async def _publish_task_event(self, task_id: str, event: str, data: Dict[str, Any]):
        queue = self.task_events.get(task_id)
        if queue:
            await queue.put({"event": event, "data": data})

    def get_task_queue(self, task_id: str) -> asyncio.Queue:
        if task_id not in self.task_events:
            self.task_events[task_id] = asyncio.Queue()
        return self.task_events[task_id]

    def _update_task_status(self, task_id: str, progress: int, step: GenerationStep):
        """Update task status in memory."""
        if task_id in self.task_status:
            self.task_status[task_id].update(
                {"progress": progress, "current_step": step}
            )

    def _build_podcast_response(self, record: dict) -> PodcastResponse:
        return PodcastResponse(
            id=record["id"],
            user_id=record["user_id"],
            title=record["title"],
            topic=record.get("topic"),
            script=record.get("script"),
            audio_url=record.get("audio_url"),
            status=PodcastStatus(record["status"]),
            duration_seconds=record.get("duration_seconds", 0),
            created_at=datetime.fromisoformat(
                record["created_at"].replace("Z", "+00:00")
            ),
            completed_at=datetime.fromisoformat(
                record["completed_at"].replace("Z", "+00:00")
            )
            if record.get("completed_at")
            else None,
        )

    async def _log_generation_step(
        self, podcast_id: str, step: str, status: str, details: str
    ):
        """Log generation step to database."""
        try:
            log_data = {
                "podcast_id": podcast_id,
                "step": step,
                "status": status,
                "details": details,
            }
            await self._execute_supabase_query(
                self.supabase.table("generation_logs").insert(log_data),
                "Create generation log",
            )
        except Exception as e:
            logger.error(f"Failed to log generation step: {str(e)}")

    async def get_generation_status(self, task_id: str) -> PodcastStatusResponse:
        """Get podcast generation status."""
        if task_id not in self.task_status:
            raise Exception("Task not found")

        status_data = self.task_status[task_id]
        return PodcastStatusResponse(
            task_id=task_id,
            status=status_data["status"],
            progress=status_data["progress"],
            current_step=status_data.get("current_step"),
            audio_url=status_data.get("audio_url"),
            error_message=status_data.get("error_message"),
        )

    async def get_list_podcasts(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> PodcastHistoryResponse:
        """Get user's podcast history."""
        try:
            result = await self._execute_supabase_query(
                self.supabase.table("podcasts")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1),
                "Get podcast history",
            )

            podcasts = [self._build_podcast_response(record) for record in result.data]

            count_result = await self._execute_supabase_query(
                self.supabase.table("podcasts")
                .select("id", count="exact")
                .eq("user_id", user_id),
                "Count podcast history",
            )
            total = count_result.count or 0

            return PodcastHistoryResponse(podcasts=podcasts, total=total)

        except Exception as e:
            logger.error(f"Get user podcasts error: {str(e)}")
            raise Exception(f"Failed to get podcasts: {str(e)}")

    async def get_podcast(self, podcast_id: str, user_id: str) -> PodcastResponse:
        """Get specific podcast details."""
        try:
            result = await self._execute_supabase_query(
                self.supabase.table("podcasts")
                .select("*")
                .eq("id", podcast_id)
                .eq("user_id", user_id),
                "Get podcast",
            )

            if not result.data:
                raise Exception("Podcast not found")

            return self._build_podcast_response(result.data[0])

        except Exception as e:
            logger.error(f"Get podcast error: {str(e)}")
            raise Exception(f"Failed to get podcast: {str(e)}")
