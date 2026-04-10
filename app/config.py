from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings managed via environment variables."""
    bot_token: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

# Initialize singletons for the application
settings = Settings()
TEMP_DIR = Path("/app/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)
