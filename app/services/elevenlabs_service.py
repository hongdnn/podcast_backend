"""
ElevenLabs text-to-speech service
"""
import logging
from typing import Optional
import uuid
import httpx
import io
from elevenlabs import generate, Voice, VoiceSettings
import requests

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
    
    # async def text_to_speech(self, text: str, voice_id: str = "nPczCjzI2devNBz1zQrb") -> bytes:
    #     """Convert text to speech using ElevenLabs API"""
    #     try:
    #         # Use the elevenlabs library for text-to-speech
    #         audio = generate(
    #             text=text,
    #             voice=Voice(
    #                 voice_id=voice_id,
    #                 settings=self.voice_settings
    #             ),
    #             api_key=self.api_key
    #         )
            
    #         # Convert generator to bytes
    #         audio_bytes = b"".join(audio)
            
    #         logger.info(f"Generated audio of size: {len(audio_bytes)} bytes")
    #         return audio_bytes
            
    #     except Exception as e:
    #         logger.error(f"Text-to-speech error: {str(e)}")
    #         raise Exception(f"Failed to generate audio: {str(e)}")
        
    async def text_to_speech(self, text: str, output_file="output.mp3", api_key="sk_a4adba4e860c0e6ba39061405b17a0e10d49cc37efea650b"):
        """
        Convert text to speech using ElevenLabs API and save as MP3.

        Args:
            text: The text to convert to speech
            output_file: The output MP3 file path (default: output.mp3)
            api_key: Your ElevenLabs API key
        """
        print("Test text:", text)
        print("Test text:", output_file)
        print("Test text:", api_key)
        voice_id = "nPczCjzI2devNBz1zQrb"  # Rachel voice
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        try:
            print(f"Converting text to speech...")
            response = requests.post(url, json=data, headers=headers)
            print('Request sent to ElevenLabs API: ', response)

            if response.status_code == 200:
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                print(f"✓ Audio saved successfully to: {output_file}")
                return output_file
            else:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")

        except Exception as e:
            print(f"An error occurred: {str(e)}")
    
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
        # try:
        #     voices = await self.get_available_voices()
            
        #     # Look for voices suitable for podcasting
        #     podcast_voices = [
        #         "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear and professional
        #         "AZnzlk1XvdvUeBnXmlld",  # Domi - warm and engaging
        #         "EXAVITQu4vr4xnSDxMaL",  # Bella - friendly and clear
        #     ]
            
        #     # Return the first available podcast voice
        #     for voice_id in podcast_voices:
        #         for voice in voices:
        #             if voice.get("voice_id") == voice_id:
        #                 logger.info(f"Using voice: {voice.get('name', 'Unknown')} ({voice_id})")
        #                 return voice_id
            
        #     # Fallback to default voice
        logger.info("Using default voice: Rachel")
        return "nPczCjzI2devNBz1zQrb"
            
        # except Exception as e:
        #     logger.error(f"Get podcast voice error: {str(e)}")
        #     return "21m00Tcm4TlvDq8ikWAM"  # Default fallback
    
    async def generate_podcast_audio(self, script: str) -> bytes:
        """Generate podcast audio with optimized settings"""
        try:
            # Get suitable voice for podcast
            voice_id = await self.get_podcast_voice()
            filename = f"podcast_{str(uuid.uuid4())}.mp3"
            
            # Generate audio with podcast-optimized settings
            output_file = await self.text_to_speech(text=script, output_file=filename)
            
            logger.info("Podcast audio generated successfully")
            return output_file
            
        except Exception as e:
            logger.error(f"Generate podcast audio error: {str(e)}")
            raise Exception(f"Failed to generate podcast audio: {str(e)}")