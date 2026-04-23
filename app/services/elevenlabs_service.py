"""
ElevenLabs text-to-speech service
"""
import logging
import random
import uuid
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    VOICE_IDS = {
        "female": [
            "EXAVITQu4vr4xnSDxMaL",  # Bella, worked with this API key
        ],
        "male": [
            "ErXwobaYiN019PkySvjV",  # Antoni, worked with this API key
        ],
    }

    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.model_id = "eleven_flash_v2_5"
        self.voice_ids = {
            **self.VOICE_IDS,
            "neutral": self.VOICE_IDS["female"] + self.VOICE_IDS["male"],
        }
    
    async def text_to_speech(self, text: str, output_file: str, voice_id: str) -> str:
        """Convert text to speech using ElevenLabs API and save as MP3."""
        if not self.api_key:
            raise Exception("Missing ELEVENLABS_API_KEY")

        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        data = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.6,
                "similarity_boost": 0.75,
                "style": 0.25,
                "use_speaker_boost": True
            }
        }
        params = {"output_format": "mp3_44100_128"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=60
                )

            if response.status_code != 200:
                logger.error(f"ElevenLabs TTS failed: {response.status_code} {response.text}")
                raise Exception(f"ElevenLabs TTS failed with status {response.status_code}: {response.text}")

            with open(output_file, "wb") as f:
                f.write(response.content)

            logger.info(f"Audio saved successfully to: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Text-to-speech error: {str(e)}")
            raise Exception(f"Failed to generate audio: {str(e)}")
    
    async def get_available_voices(self) -> list:
        """Get list of available voices"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json"
                }
                
                response = await client.get(
                    f"{self.base_url}/voices",
                    headers=headers
                )
                
                if response.status_code == 200:
                    voices_data = response.json()
                    return voices_data.get("voices", [])
                else:
                    logger.error(f"Failed to get voices: {response.status_code} {response.text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get voices error: {str(e)}")
            return []

    async def get_podcast_voice(self, voice_preference: str = "neutral") -> str:
        """Pick a random English voice based on requested gender preference."""
        preference = (voice_preference or "neutral").strip().lower()
        if preference not in self.voice_ids:
            preference = "neutral"

        voice_id = random.choice(self.voice_ids[preference])
        logger.info(f"Using {preference} English voice: {voice_id}")
        return voice_id
    
    async def generate_podcast_audio(self, script: str, voice_preference: str = "neutral") -> bytes:
        """Generate podcast audio with optimized settings"""
        try:
            # Get suitable voice for podcast
            voice_id = await self.get_podcast_voice(voice_preference)
            filename = f"podcast_{str(uuid.uuid4())}.mp3"
            
            # Generate audio with podcast-optimized settings
            output_file = await self.text_to_speech(
                text=script,
                output_file=filename,
                voice_id=voice_id
            )
            
            logger.info("Podcast audio generated successfully")
            return output_file
            
        except Exception as e:
            logger.error(f"Generate podcast audio error: {str(e)}")
            raise Exception(f"Failed to generate podcast audio: {str(e)}")
