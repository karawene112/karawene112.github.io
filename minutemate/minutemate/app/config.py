"""App settings, read from environment variables (or a .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class Settings:
    # App
    APP_NAME = _get("APP_NAME", "MinuteMate")
    APP_PASSWORD = _get("APP_PASSWORD", "change-me")
    SECRET_KEY = _get("SECRET_KEY", "dev-secret-change-me")
    PUBLIC_BASE_URL = _get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    DATA_DIR = Path(_get("DATA_DIR", str(BASE_DIR / "data")))

    # Recall.ai (meeting bot + transcription)
    RECALL_API_KEY = _get("RECALL_API_KEY")
    RECALL_REGION = _get("RECALL_REGION", "us-east-1")
    WEBHOOK_TOKEN = _get("WEBHOOK_TOKEN", "change-this-webhook-token")
    BOT_NAME = _get("BOT_NAME", "MinuteMate Notetaker")
    TRANSCRIPT_LANGUAGE = _get("TRANSCRIPT_LANGUAGE", "auto")  # "auto" = detect (Arabic/French/English...)

    # Claude (summary)
    ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
    CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-sonnet-5-5")

    # Email (SMTP)
    SMTP_HOST = _get("SMTP_HOST")
    SMTP_PORT = int(_get("SMTP_PORT", "587"))
    SMTP_USER = _get("SMTP_USER")
    SMTP_PASSWORD = _get("SMTP_PASSWORD")
    SMTP_FROM = _get("SMTP_FROM") or _get("SMTP_USER")

    # Background status check (backup if webhooks can't reach you, e.g. on localhost)
    POLL_SECONDS = int(_get("POLL_SECONDS", "60"))

    @property
    def recall_base(self) -> str:
        return f"https://{self.RECALL_REGION}.recall.ai/api/v1"

    @property
    def email_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "files").mkdir(parents=True, exist_ok=True)
