"""
Google AI service for Gemini LLM and Google Search integration
"""
import logging
from typing import List, Dict, Any
import google.generativeai as genai
from serpapi import GoogleSearch
import asyncio
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

class GoogleAIService:
    def __init__(self):
        # Configure Google AI
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
    async def search_latest_news(self, topic: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """Search for latest news using Google Search"""
        try:
            # Use SerpAPI for Google Search (you'll need to get an API key)
            # For now, we'll simulate with a basic search
            search_query = f"{topic} latest news 2024"
            
            # Using httpx for async HTTP requests to simulate news search
            async with httpx.AsyncClient() as client:
                # This is a placeholder - in production you'd use SerpAPI or Google Custom Search API
                # For hackathon purposes, we'll return mock data
                mock_news = [
                    {
                        "title": f"Latest developments in {topic}",
                        "snippet": f"Recent breakthrough in {topic} technology shows promising results...",
                        "link": "https://example.com/news1",
                        "date": "2024-01-15"
                    },
                    {
                        "title": f"{topic} industry trends for 2024",
                        "snippet": f"Experts predict significant growth in {topic} sector this year...",
                        "link": "https://example.com/news2", 
                        "date": "2024-01-14"
                    },
                    {
                        "title": f"Innovation in {topic} reaches new heights",
                        "snippet": f"Companies are investing heavily in {topic} research and development...",
                        "link": "https://example.com/news3",
                        "date": "2024-01-13"
                    }
                ]
                
                logger.info(f"Found {len(mock_news)} news articles for topic: {topic}")
                return mock_news[:num_results]
                
        except Exception as e:
            logger.error(f"News search error: {str(e)}")
            raise Exception(f"Failed to search news: {str(e)}")
    
    async def generate_podcast_script(self, news_data: List[Dict[str, Any]], topic: str, duration: int = 5) -> str:
        """Generate natural podcast script from news data"""
        try:
            # Prepare news content for the prompt
            news_content = ""
            for i, article in enumerate(news_data, 1):
                news_content += f"{i}. {article['title']}\n"
                news_content += f"   {article['snippet']}\n\n"
            
            # Create the prompt for natural podcast script generation
            prompt = f"""
You are a professional podcast host creating an engaging {duration}-minute podcast episode about {topic}.

Based on the following recent news articles, create a natural, conversational podcast script that sounds like a real podcast host talking to their audience:

NEWS ARTICLES:
{news_content}

REQUIREMENTS:
- Create a {duration}-minute podcast script (approximately {duration * 150} words)
- Use a conversational, engaging tone like a real podcast host
- Include natural transitions between topics
- Add personal commentary and insights
- Include an engaging introduction and conclusion
- Make it sound natural when spoken aloud
- Use phrases like "Hey everyone", "What's interesting is...", "Let me tell you about..."
- Include natural pauses and emphasis markers like [pause], [emphasis]

SCRIPT FORMAT:
[INTRO MUSIC FADES]

Host: [Your natural, engaging podcast script here]

[OUTRO MUSIC FADES IN]

Generate the complete podcast script now:
"""

            # Generate script using Gemini
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            
            if not response.text:
                raise Exception("Failed to generate script")
            
            logger.info(f"Generated podcast script of length: {len(response.text)}")
            return response.text
            
        except Exception as e:
            logger.error(f"Script generation error: {str(e)}")
            raise Exception(f"Failed to generate script: {str(e)}")
    
    async def enhance_script_for_audio(self, script: str) -> str:
        """Enhance script for better text-to-speech conversion"""
        try:
            enhancement_prompt = f"""
Take this podcast script and optimize it for text-to-speech conversion:

ORIGINAL SCRIPT:
{script}

REQUIREMENTS:
- Remove any stage directions or music cues
- Ensure all text is speakable
- Add natural pauses with commas and periods
- Spell out numbers and abbreviations
- Make sure pronunciation is clear
- Keep the conversational tone
- Remove any special characters that might confuse TTS

Return only the enhanced script text that's ready for text-to-speech:
"""

            response = await asyncio.to_thread(
                self.model.generate_content,
                enhancement_prompt
            )
            
            if not response.text:
                return script  # Return original if enhancement fails
            
            logger.info("Script enhanced for TTS conversion")
            return response.text
            
        except Exception as e:
            logger.error(f"Script enhancement error: {str(e)}")
            return script  # Return original script if enhancement fails