"""
ElevenLabs text-to-speech service
"""
import logging
from typing import Optional
import httpx
import io
from elevenlabs import generate, Voice, VoiceSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Default voice settings for podcast-style speech
        self.voice_settings = VoiceSettings(
            stability=0.75,
            similarity_boost=0.75,
            style=0.5,
            use_speaker_boost=True
        )
    
    async def text_to_speech(self, text: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> bytes:
        """Convert text to speech using ElevenLabs API"""
        try:
            # Use the elevenlabs library for text-to-speech
            audio = generate(
                text=text,
                voice=Voice(
                    voice_id=voice_id,
                    settings=self.voice_settings
                ),
                api_key=self.api_key
            )
            
            # Convert generator to bytes
            audio_bytes = b"".join(audio)
            
            logger.info(f"Generated audio of size: {len(audio_bytes)} bytes")
            return audio_bytes
            
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
                    logger.error(f"Failed to get voices: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get voices error: {str(e)}")
            return []
    
    async def get_podcast_voice(self) -> str:
        """Get a suitable voice ID for podcast content"""
        try:
            voices = await self.get_available_voices()
            
            # Look for voices suitable for podcasting
            podcast_voices = [
                "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear and professional
                "AZnzlk1XvdvUeBnXmlld",  # Domi - warm and engaging
                "EXAVITQu4vr4xnSDxMaL",  # Bella - friendly and clear
            ]
            
            # Return the first available podcast voice
            for voice_id in podcast_voices:
                for voice in voices:
                    if voice.get("voice_id") == voice_id:
                        logger.info(f"Using voice: {voice.get('name', 'Unknown')} ({voice_id})")
                        return voice_id
            
            # Fallback to default voice
            logger.info("Using default voice: Rachel")
            return "21m00Tcm4TlvDq8ikWAM"
            
        except Exception as e:
            logger.error(f"Get podcast voice error: {str(e)}")
            return "21m00Tcm4TlvDq8ikWAM"  # Default fallback
    
    async def generate_podcast_audio(self, script: str) -> bytes:
        """Generate podcast audio with optimized settings"""
        try:
            # Get suitable voice for podcast
            voice_id = await self.get_podcast_voice()
            
            # Generate audio with podcast-optimized settings
            audio_bytes = await self.text_to_speech(script, voice_id)
            
            logger.info("Podcast audio generated successfully")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Generate podcast audio error: {str(e)}")
            raise Exception(f"Failed to generate podcast audio: {str(e)}")