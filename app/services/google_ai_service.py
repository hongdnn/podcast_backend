"""
Google AI service for Gemini LLM and Vertex AI Search integration.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List

import google.generativeai as genai
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleAIService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def search_latest_news(self, topic: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """Search for latest news using Vertex AI Search searchLite."""
        try:
            search_query = f"{topic} industry today latest news"

            url = (
                "https://discoveryengine.googleapis.com/v1/"
                f"projects/{settings.vertex_project_id}/"
                f"locations/{settings.vertex_search_location}/"
                "collections/default_collection/"
                f"engines/{settings.search_engine_id}/"
                f"servingConfigs/{settings.vertex_search_serving_config}:searchLite"
            )
            params = {"key": settings.google_search_api_key}
            payload = {
                "query": search_query,
                "pageSize": num_results
            }
            if settings.vertex_search_filter:
                payload["filter"] = settings.vertex_search_filter

            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", []):
                document = item.get("document", {})
                struct_data = document.get("structData", {}) or {}
                derived_data = document.get("derivedStructData", {}) or {}
                article_data = {**struct_data, **derived_data}

                title = article_data.get("title") or document.get("name", "Untitled")
                snippet = self._extract_vertex_snippet(article_data)
                link = (
                    article_data.get("link")
                    or article_data.get("uri")
                    or article_data.get("url")
                )

                if title or snippet:
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": link
                    })

            logger.info(f"Found {len(results)} news articles for topic: {topic}")
            return results

        except Exception as e:
            logger.error(f"News search error: {str(e)}")
            raise Exception(f"Failed to search news: {str(e)}")

    def _extract_vertex_snippet(self, article_data: Dict[str, Any]) -> str:
        snippets = article_data.get("snippets")
        if isinstance(snippets, list) and snippets:
            first_snippet = snippets[0]
            if isinstance(first_snippet, dict):
                return (
                    first_snippet.get("snippet")
                    or first_snippet.get("htmlSnippet")
                    or ""
                )
            if isinstance(first_snippet, str):
                return first_snippet

        return (
            article_data.get("snippet")
            or article_data.get("htmlSnippet")
            or article_data.get("description")
            or ""
        )

    # Previous Google Custom Search implementation, kept for reference:
    #
    # async def search_latest_news(self, topic: str, num_results: int = 10) -> List[Dict[str, Any]]:
    #     """Search for latest news using Google Custom Search."""
    #     try:
    #         search_query = f"{topic} industry today latest news"
    #         url = "https://www.googleapis.com/customsearch/v1"
    #         params = {
    #             "key": settings.google_search_api_key,
    #             "cx": settings.search_engine_id,
    #             "q": search_query,
    #         }
    #         async with httpx.AsyncClient() as client:
    #             response = await client.get(url, params=params, timeout=30)
    #             response.raise_for_status()
    #             data = response.json()
    #
    #         results = []
    #         for item in data.get("items", []):
    #             results.append({
    #                 "title": item.get("title"),
    #                 "snippet": item.get("snippet"),
    #                 "url": item.get("link")
    #             })
    #
    #         logger.info(f"Found {len(results)} news articles for topic: {topic}")
    #         return results
    #
    #     except Exception as e:
    #         logger.error(f"News search error: {str(e)}")
    #         raise Exception(f"Failed to search news: {str(e)}")

    async def generate_podcast_script(self, news_data: List[Dict[str, Any]], topic: str, duration: int = 5) -> str:
        """Generate a natural podcast script for one speaker, TTS-ready."""
        try:
            news_content = ""
            for i, article in enumerate(news_data, 1):
                news_content += f"{i}. {article['title']}\n"
                news_content += f"   {article['snippet']}\n"
                if article.get("url"):
                    news_content += f"   Source: {article['url']}\n"
                news_content += "\n"

            prompt = f"""
You are the host of Podcastify.

Write only the exact words the host will speak aloud for an engaging {duration}-minute episode about {topic}.

Rules:
- The show name is Podcastify.
- Do not invent another podcast name.
- Do not include speaker labels.
- Do not include markdown.
- Do not include stage directions.
- Do not include music cues.
- Do not include text in parentheses or brackets.
- Do not say "intro music" or "outro music".
- Do not open with say hi everyone or introduce yourself as the host.
- Speak directly to one listener in a personal tone.
- Start with a natural welcome that mentions Podcastify.
- End with a natural goodbye that mentions Podcastify.
- Use a conversational, engaging tone.
- Include natural transitions and personal commentary.
- Spell out numbers and abbreviations when that will sound better in text-to-speech.

NEWS ARTICLES:
{news_content}

Generate only the spoken script now:
"""

            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )

            if not response.text:
                raise Exception("Failed to generate podcast script")

            script = self.sanitize_script_for_tts(response.text)

            logger.info(f"Generated podcast script (single speaker, TTS-ready) length: {len(script)}")
            return script

        except Exception as e:
            logger.error(f"Script generation error: {str(e)}")
            raise Exception(f"Failed to generate podcast script: {str(e)}")

    def sanitize_script_for_tts(self, script: str) -> str:
        """Remove non-spoken formatting that should never be sent to TTS."""
        cleaned = script.strip()
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"^\s*(host|podcastify host|narrator)\s*:\s*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
        cleaned = re.sub(r"\([^)]*(music|fade|cue|sfx|sound|intro|outro)[^)]*\)", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[[^\]]*(music|fade|cue|sfx|sound|intro|outro)[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*[-*_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
