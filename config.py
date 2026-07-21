import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Telegram API (for Telethon user clients)
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")

    # AWS Bedrock Mantle (GLM-5) Configuration
    AWS_BEARER_TOKEN: str = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
    AWS_REGION: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    AI_MODEL: str = os.getenv("DEFAULT_MODEL", "zai.glm-5")
    AVAILABLE_MODELS: list = os.getenv("AVAILABLE_MODELS", "zai.glm-5").split(",")

    # Bedrock Mantle API endpoint (OpenAI-compatible)
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", f"https://bedrock-mantle.{os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}.api.aws/v1")

    # Session storage channel (bot must be admin in this channel)
    SESSION_CHANNEL_ID: int = int(os.getenv("SESSION_CHANNEL_ID", "-1003547640478"))

    # Database (for chat history & command logs only)
    DB_PATH: str = os.getenv("DB_PATH", "bot_database.db")

    # Limits
    MAX_HISTORY_MESSAGES: int = 50
    AI_MAX_TOKENS: int = 4096


config = Config()
