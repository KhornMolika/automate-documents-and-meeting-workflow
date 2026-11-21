from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_NAME: str = "ACLEDA University Document & Meeting Workflow"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    # Defaults to SQLite if not provided, allowing zero-friction local development and testing
    DATABASE_URL: str = "sqlite+aiosqlite:///./aub_workflow.db"
    DATABASE_URL_SYNC: str = "sqlite:///./aub_workflow.db"

    # Security & JWT
    SECRET_KEY: str = "acleda_development_secret_key_change_in_production_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_FALLBACK_MODELS: List[str] = ["gemini-3.5-flash-lite", "gemini-3-flash-preview"]
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_TOTAL_TIMEOUT_SECONDS: int = 120

    # Optional Google Drive publishing for verified minutes
    GOOGLE_DRIVE_CLIENT_ID: str = ""
    GOOGLE_DRIVE_CLIENT_SECRET: str = ""
    GOOGLE_DRIVE_REFRESH_TOKEN: str = ""
    GOOGLE_DRIVE_FOLDER_ID: str = ""

    # Generative LLM provider: auto | gemini | ollama | opencode
    # auto uses Gemini when GEMINI_API_KEY is set, otherwise the local Ollama model.
    LLM_PROVIDER: str = "auto"
    AUTO_SUMMARIZE_ON_UPLOAD: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT_SECONDS: int = 300
    OPENCODE_BASE_URL: str = "https://opencode.ai/inference/openai/v1"
    OPENCODE_API_KEY: str = ""
    OPENCODE_MODEL: str = "gemini-3.1-flash-lite"
    OPENCODE_SESSION: str = "aub-workflow"

    # File storage limits
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "xlsx", "csv"]

    # Local speech service (batch transcription only)
    SPEECH_SERVICE_URL: str = "http://localhost:8001"
    SPEECH_TIMEOUT_SECONDS: int = 3600
    MAX_RECORDING_SIZE_MB: int = 500
    ALLOWED_RECORDING_EXTENSIONS: List[str] = [
        "mp4", "m4a", "mp3", "wav", "webm", "ogg", "aac", "flac", "mov",
    ]
    ALLOWED_TRANSCRIPT_EXTENSIONS: List[str] = ["txt", "vtt", "srt", "docx"]


settings = Settings()
