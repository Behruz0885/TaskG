import os
import logging
import io
import aiohttp
from config import config

logger = logging.getLogger(__name__)


async def transcribe_voice(voice_bytes: bytes, filename: str = "voice.ogg") -> str | None:
    """
    Transcribe Telegram voice/audio file bytes to text using available STT services.
    Supports Groq Whisper, OpenAI Whisper, or Wit.ai API.
    """
    # 1. Try Groq Whisper API (Fastest & Free)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            text = await _transcribe_groq(voice_bytes, filename, groq_key)
            if text:
                return text
        except Exception as e:
            logger.warning(f"Groq STT failed: {e}")

    # 2. Try OpenAI Whisper API
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            text = await _transcribe_openai(voice_bytes, filename, openai_key)
            if text:
                return text
        except Exception as e:
            logger.warning(f"OpenAI STT failed: {e}")

    # 3. Try Wit.ai Free API
    wit_token = os.getenv("WIT_AI_TOKEN", "")
    if wit_token:
        try:
            text = await _transcribe_witai(voice_bytes, wit_token)
            if text:
                return text
        except Exception as e:
            logger.warning(f"Wit.ai STT failed: {e}")

    # 4. Try Free Google Speech API (No API key needed!)
    try:
        text = await _transcribe_google_free(voice_bytes)
        if text:
            return text
    except Exception as e:
        logger.warning(f"Google Free STT failed: {e}")

    logger.error("All STT transcription methods failed")
    return None


async def _transcribe_groq(file_bytes: bytes, filename: str, api_key: str) -> str | None:
    """Transcribe using Groq Whisper API."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    data = aiohttp.FormData()
    data.add_field("file", file_bytes, filename=filename, content_type="audio/ogg")
    data.add_field("model", "whisper-large-v3")
    data.add_field("response_format", "json")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 200:
                res = await resp.json()
                return res.get("text", "").strip()
            else:
                err = await resp.text()
                logger.error(f"Groq STT error {resp.status}: {err[:200]}")
                return None


async def _transcribe_openai(file_bytes: bytes, filename: str, api_key: str) -> str | None:
    """Transcribe using OpenAI Whisper API."""
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    data = aiohttp.FormData()
    data.add_field("file", file_bytes, filename=filename, content_type="audio/ogg")
    data.add_field("model", "whisper-1")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 200:
                res = await resp.json()
                return res.get("text", "").strip()
            else:
                err = await resp.text()
                logger.error(f"OpenAI STT error {resp.status}: {err[:200]}")
                return None


async def _transcribe_witai(file_bytes: bytes, token: str) -> str | None:
    """Transcribe using Wit.ai Speech API."""
    url = "https://api.wit.ai/speech"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "audio/ogg",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, headers=headers, data=file_bytes, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 200:
                res = await resp.json()
                return res.get("text", "").strip()
            else:
                err = await resp.text()
                logger.error(f"Wit.ai STT error {resp.status}: {err[:200]}")
                return None


async def _transcribe_google_free(file_bytes: bytes) -> str | None:
    """
    Free fallback Speech-to-Text using Google Speech Recognition.
    Requires ZERO API keys!
    """
    url = "https://www.google.com/speech-api/v2/recognize?client=chromium&lang=uz-UZ"
    headers = {"Content-Type": "audio/ogg; rate=48000"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, data=file_bytes, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 200:
                    text_resp = await resp.text()
                    for line in text_resp.splitlines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if "result" in data and len(data["result"]) > 0:
                                alt = data["result"][0].get("alternative", [])
                                if alt and len(alt) > 0:
                                    return alt[0].get("transcript", "").strip()
                        except Exception:
                            pass
    except Exception as e:
        logger.warning(f"Google free STT request failed: {e}")
    return None
