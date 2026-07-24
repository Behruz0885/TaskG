"""
Offline Text-to-Speech for outgoing Telegram voice messages.

Uses Microsoft Edge-TTS (free, no API key) to synthesize speech, then converts
it to the OGG/Opus format Telegram needs to render a real voice bubble.

No cloud API tokens are required. Based on the "telegram-offline-voice" skill
by @sanwecn, adapted for the bot's uz/ru/en (and zh) languages.
"""
import os
import re
import html
import shutil
import asyncio
import logging
import tempfile

logger = logging.getLogger(__name__)

# Default Edge-TTS voice per language. Override any of them with an env var,
# e.g. TTS_VOICE_UZ=uz-UZ-SardorNeural
_DEFAULT_VOICES = {
    "uz": "uz-UZ-MadinaNeural",   # female, natural
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-AriaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}

# Speaking rate, e.g. "+0%", "+5%", "-10%".
_TTS_RATE = os.getenv("TTS_RATE", "+0%")

# Cap the amount of text we synthesize so voice notes stay short and fast.
_MAX_TTS_CHARS = 1500

# Substrings that signal the user wants a spoken / voice reply from the AI.
# Uzbek stems, Russian stems, and English words.
_VOICE_TRIGGERS = (
    # Uzbek
    "ovoz", "gapir", "gaplash", "eshittir",
    # Russian
    "голос", "озвуч", "проговор", "аудио",
    # English
    "voice", "speak", "aloud", "tts",
)


def wants_voice_reply(text: str) -> bool:
    """Return True if the user's message asks the AI to answer with voice/audio."""
    if not text:
        return False
    low = text.lower()
    return any(trigger in low for trigger in _VOICE_TRIGGERS)


def clean_for_tts(text: str) -> str:
    """Strip HTML/Markdown/URLs so the engine doesn't read out markup symbols."""
    if not text:
        return ""
    t = text
    t = re.sub(r"<[^>]+>", " ", t)          # HTML tags
    t = html.unescape(t)                     # &amp; -> &, etc.
    t = re.sub(r"https?://\S+", " ", t)      # URLs
    t = re.sub(r"[*_`#>]+", " ", t)          # markdown emphasis/code/quote/heading
    t = re.sub(r"[-=]{3,}", " ", t)          # horizontal rules
    t = re.sub(r"\s+", " ", t).strip()       # collapse whitespace
    return t


async def _resolve_ffmpeg() -> str | None:
    """Find an ffmpeg binary: prefer the system one, else a pip-bundled static build."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


async def text_to_voice_ogg(text: str, language: str = "uz") -> bytes | None:
    """Synthesize `text` into Telegram-ready OGG/Opus bytes, or None on any failure.

    The caller should fall back to a plain text reply when this returns None.
    """
    try:
        import edge_tts
    except Exception as e:
        logger.warning(f"edge-tts not available: {e}")
        return None

    clean = clean_for_tts(text)
    if not clean:
        return None
    if len(clean) > _MAX_TTS_CHARS:
        clean = clean[:_MAX_TTS_CHARS].rsplit(" ", 1)[0] + "…"

    voice = os.getenv(f"TTS_VOICE_{language.upper()}") or _DEFAULT_VOICES.get(
        language, _DEFAULT_VOICES["uz"]
    )

    ffmpeg = await _resolve_ffmpeg()
    if not ffmpeg:
        logger.error("ffmpeg not found; cannot produce an OGG voice message")
        return None

    mp3_path = ogg_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name

        # Generate MP3 through the Python API (text passed as an argument, so
        # there is no shell and no command-injection surface).
        communicate = edge_tts.Communicate(clean, voice, rate=_TTS_RATE)
        await communicate.save(mp3_path)

        if not os.path.getsize(mp3_path):
            logger.error("edge-tts produced empty audio")
            return None

        ogg_path = mp3_path[:-4] + ".ogg"
        proc = await asyncio.create_subprocess_exec(
            ffmpeg, "-y", "-loglevel", "error",
            "-i", mp3_path,
            "-c:a", "libopus", "-b:a", "48k", "-ac", "1", "-ar", "48000",
            "-application", "voip",
            ogg_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not os.path.exists(ogg_path) or not os.path.getsize(ogg_path):
            logger.error(
                f"ffmpeg conversion failed (code {proc.returncode}): "
                f"{stderr.decode('utf-8', 'ignore')[:200]}"
            )
            return None

        with open(ogg_path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None
    finally:
        for p in (mp3_path, ogg_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
