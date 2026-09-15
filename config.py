import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    openai_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.6")
    exchange_id: str = os.getenv("EXCHANGE_ID", "binance")
    candle_limit: int = int(os.getenv("CANDLE_LIMIT", "500"))
    cache_seconds: int = int(os.getenv("CACHE_SECONDS", "15"))
    max_image_mb: int = int(os.getenv("MAX_IMAGE_MB", "10"))

settings = Settings()

if not settings.telegram_token:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
if not settings.openai_key:
    raise RuntimeError("OPENAI_API_KEY is missing")
