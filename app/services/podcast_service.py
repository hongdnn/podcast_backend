"""
Main podcast service that orchestrates podcast generation.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

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
from app.services.email_service import EmailService
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
        self.email_service = EmailService()

        # In-memory queue/status simulation. Use Redis/Kafka/Postgres LISTEN in production.
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.scheduler_task: Optional[asyncio.Task] = None
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
            if self.scheduler_task and not self.scheduler_task.done():
                return

        self.worker_task = asyncio.create_task(self._worker_loop())
        # self.scheduler_task = asyncio.create_task(self._scheduled_delivery_loop())
        logger.info("Podcast queue worker started")
        # logger.info("Podcast delivery scheduler started")

    async def stop_worker(self):
        tasks = [task for task in (self.worker_task, self.scheduler_task) if task]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.worker_task = None
        self.scheduler_task = None
        logger.info("Podcast queue worker stopped")
        logger.info("Podcast delivery scheduler stopped")

    async def _worker_loop(self):
        while True:
            job = await self.job_queue.get()
            try:
                await self.generate_podcast(**job)
            finally:
                self.job_queue.task_done()

    async def _scheduled_delivery_loop(self):
        while True:
            try:
                users = await self._load_scheduled_delivery_users()
                await self._enqueue_due_scheduled_deliveries(users)
                sleep_seconds = self._seconds_until_next_scheduled_scan(users)
            except Exception as e:
                logger.error("Scheduled delivery scan failed: %s", str(e))
                sleep_seconds = 60

            await asyncio.sleep(sleep_seconds)

    async def _load_scheduled_delivery_users(self) -> list[dict]:
        result = await self._execute_supabase_query(
            self.supabase.table("users")
            .select(
                "id,email,name,preferences,daily_delivery_time,timezone,last_scheduled_delivery_date"
            ),
            "Load scheduled delivery users",
        )
        return result.data or []

    async def _enqueue_due_scheduled_deliveries(self, users: list[dict]):
        now_utc = datetime.now(timezone.utc)

        for user in users:
            if not self._is_user_due_for_delivery(user, now_utc):
                continue

            task_id = str(uuid.uuid4())
            await self.register_task(task_id, user["id"])
            await self.enqueue_generation(
                task_id=task_id,
                user_id=user["id"],
                topic=user.get("preferences") or "technology",
                duration=5,
                voice_preference="neutral",
                scheduled_delivery=True,
                recipient_email=user.get("email"),
                recipient_name=user.get("name") or "there",
            )
            await self._mark_user_scheduled_for_today(user, now_utc)
            logger.info(
                "Scheduled daily podcast task %s for user %s at %s %s",
                task_id,
                user["id"],
                user.get("daily_delivery_time"),
                user.get("timezone"),
            )

    def _is_user_due_for_delivery(self, user: dict, now_utc: datetime) -> bool:
        delivery_time = user.get("daily_delivery_time")
        timezone_name = user.get("timezone")
        if not delivery_time or not timezone_name:
            return False

        try:
            local_now = now_utc.astimezone(ZoneInfo(timezone_name))
            target_hour, target_minute = self._parse_delivery_time(delivery_time)
        except Exception:
            logger.warning(
                "Skipping scheduled delivery for user %s due to invalid schedule %s / %s",
                user.get("id"),
                delivery_time,
                timezone_name,
            )
            return False

        last_delivery_date = user.get("last_scheduled_delivery_date")
        if last_delivery_date:
            last_delivery_date = str(last_delivery_date)
            if last_delivery_date == local_now.date().isoformat():
                return False

        return (
            local_now.hour == target_hour
            and local_now.minute == target_minute
        )

    def _seconds_until_next_scheduled_scan(self, users: list[dict]) -> int:
        now_utc = datetime.now(timezone.utc)
        next_run_at: datetime | None = None

        for user in users:
            candidate = self._next_delivery_datetime_utc(user, now_utc)
            if candidate is None:
                continue
            if next_run_at is None or candidate < next_run_at:
                next_run_at = candidate

        if next_run_at is None:
            return 1800

        # Wake a few seconds after the slot begins so hour/minute comparisons are stable.
        target = next_run_at + timedelta(seconds=5)
        delay = int((target - now_utc).total_seconds())
        return max(delay, 30)

    def _next_delivery_datetime_utc(
        self, user: dict, now_utc: datetime
    ) -> Optional[datetime]:
        delivery_time = user.get("daily_delivery_time")
        timezone_name = user.get("timezone")
        if not delivery_time or not timezone_name:
            return None

        try:
            local_tz = ZoneInfo(timezone_name)
            local_now = now_utc.astimezone(local_tz)
            target_hour, target_minute = self._parse_delivery_time(delivery_time)
        except Exception:
            return None

        local_target = local_now.replace(
            hour=target_hour,
            minute=target_minute,
            second=0,
            microsecond=0,
        )
        if local_target <= local_now:
            local_target = local_target + timedelta(days=1)

        return local_target.astimezone(timezone.utc)

    def _parse_delivery_time(self, delivery_time: str) -> tuple[int, int]:
        target_hour, target_minute = [
            int(part) for part in str(delivery_time).split(":", 1)
        ]
        if target_minute not in (0, 30):
            raise ValueError("Delivery time must be in 30-minute increments")
        return target_hour, target_minute

    async def _mark_user_scheduled_for_today(self, user: dict, now_utc: datetime):
        timezone_name = user.get("timezone") or "UTC"
        local_date = now_utc.astimezone(ZoneInfo(timezone_name)).date().isoformat()
        await self._execute_supabase_query(
            self.supabase.table("users")
            .update(
                {
                    "last_scheduled_delivery_date": local_date,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", user["id"]),
            "Mark user scheduled delivery date",
        )

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
        scheduled_delivery: bool = False,
        recipient_email: Optional[str] = None,
        recipient_name: Optional[str] = None,
    ):
        await self.job_queue.put(
            {
                "task_id": task_id,
                "user_id": user_id,
                "topic": topic,
                "duration": duration,
                "voice_preference": voice_preference,
                "scheduled_delivery": scheduled_delivery,
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
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
        scheduled_delivery: bool = False,
        recipient_email: Optional[str] = None,
        recipient_name: Optional[str] = None,
    ) -> Optional[PodcastResponse]:
        """Run podcast generation in the background."""
        output_file: Optional[str] = None
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
            await self._delete_local_file(output_file)
            output_file = None

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

            if scheduled_delivery and recipient_email:
                await self.email_service.send_scheduled_podcast_email(
                    recipient_email=recipient_email,
                    recipient_name=recipient_name or "there",
                    podcast_title=podcast.title,
                    podcast_topic=podcast.topic or search_topic,
                    audio_url=podcast.audio_url or "",
                )

            logger.info(f"Podcast generation completed for task: {task_id} using {storage_provider}")
            return podcast

        except Exception as e:
            await self._delete_local_file(output_file)
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

    async def _delete_local_file(self, file_path: Optional[str]) -> None:
        if not file_path:
            return

        try:
            await asyncio.to_thread(os.remove, file_path)
            logger.info("Deleted local temporary file: %s", file_path)
        except FileNotFoundError:
            return
        except Exception as e:
            logger.warning(
                "Failed to delete local temporary file %s: %s",
                file_path,
                str(e),
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
