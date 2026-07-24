import os
import json
import logging
import io
import aiohttp
from config import config

logger = logging.getLogger(__name__)


async def transcribe_voice(voice_bytes: bytes, filename: str = "voice.ogg") -> str | None:
    """
    Transcribe Telegram voice/audio file bytes to text using available STT services.
    Supports Voxtral, Groq Whisper, OpenAI Whisper, or Wit.ai API.
    """
    # 1. Try AWS Bedrock Voxtral Multimodal transcription (Highest quality voice-in text-out)
    try:
        text = await _transcribe_voxtral(voice_bytes)
        if text:
            logger.info(f"Voxtral STT successfully transcribed: '{text[:50]}...'")
            return text
    except Exception as e:
        logger.warning(f"Voxtral STT failed, falling back to other services: {e}")

    # 2. Try Groq Whisper API (Fastest & Free)
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


async def _convert_ogg_to_wav(ogg_bytes: bytes) -> bytes | None:
    """Convert OGG/Opus bytes to standard WAV bytes using ffmpeg for Bedrock multimodal model compatibility."""
    import tempfile
    import shutil
    import asyncio
    
    # Resolve ffmpeg binary
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
            
    if not ffmpeg:
        logger.error("ffmpeg binary not found, cannot convert audio to WAV")
        return None
        
    ogg_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            ogg_path = f.name
            f.write(ogg_bytes)
            
        wav_path = ogg_path[:-4] + ".wav"
        
        proc = await asyncio.create_subprocess_exec(
            ffmpeg, "-y", "-loglevel", "error",
            "-i", ogg_path,
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            wav_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not os.path.exists(wav_path) or not os.path.getsize(wav_path):
            logger.error(f"ffmpeg conversion to WAV failed (code {proc.returncode}): {stderr.decode('utf-8', 'ignore')[:200]}")
            return None
            
        with open(wav_path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error converting OGG to WAV: {e}")
        return None
    finally:
        for p in (ogg_path, wav_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


async def _transcribe_voxtral(voice_bytes: bytes) -> str | None:
    """Transcribe using AWS Bedrock Voxtral multimodal model."""
    token = config.AWS_BEARER_TOKEN
    if not token:
        logger.warning("AWS_BEARER_TOKEN not set, cannot use Voxtral STT")
        return None
        
    try:
        # Convert OGG to WAV first so the model can decode the audio successfully
        wav_bytes = await _convert_ogg_to_wav(voice_bytes)
        if not wav_bytes:
            logger.warning("Failed to convert voice OGG to WAV for Voxtral")
            return None

        import base64
        voice_b64 = base64.b64encode(wav_bytes).decode("utf-8")
        
        payload = {
            "model": "mistral.voxtral-small-24b-2507",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "SYSTEM INSTRUCTION:\n"
                                "You are a precise Speech-to-Text transcriber. Your ONLY task is to listen to the audio and write down exactly what was said in text format.\n"
                                "CRITICAL RULES:\n"
                                "1. Do NOT answer any questions in the audio.\n"
                                "2. Do NOT reply conversationally.\n"
                                "3. Do NOT add any notes, greetings, explanations, or corrections.\n"
                                "4. Output ONLY the word-for-word transcription of the spoken audio.\n"
                                "5. If the audio is silent or contains no speech, output an empty string.\n\n"
                                "Example: If user says 'Assalomu alaykum', you must output: 'Assalomu alaykum'. Do NOT write 'Vaalaykum assalom, qanday yordam bera olaman?'."
                            )
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": voice_b64,
                                "format": "wav"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.0,
        }
        
        base_url = getattr(config, "AI_BASE_URL", "").strip() or os.getenv("AI_BASE_URL", "")
        if not base_url or "amazonaws.com" in base_url:
            region = config.AWS_REGION
            base_url = f"https://bedrock-mantle.{region}.api.aws/v1"
        base_url = base_url.rstrip("/")
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=40)
            ) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    if "choices" in res and len(res["choices"]) > 0:
                        content = res["choices"][0]["message"].get("content", "").strip()
                        return content
                else:
                    err = await resp.text()
                    logger.error(f"Voxtral STT error {resp.status}: {err[:200]}")
    except Exception as e:
        logger.warning(f"Voxtral STT request failed: {e}")
    return None
