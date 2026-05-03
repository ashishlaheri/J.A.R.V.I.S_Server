"""Centralized configuration — reads from .env once, used everywhere."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # AI
    AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # Auth
    JARVIS_PASSWORD = os.getenv("JARVIS_PASSWORD", "jarvis")
    JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_DAYS = 30

    # Weather
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    WEATHER_CITY = os.getenv("WEATHER_CITY", "Delhi")

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DB_PATH = os.path.join(DATA_DIR, "jarvis.db")

    # TTS
    TTS_VOICE = "en-GB-RyanNeural"

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.DATA_DIR, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
