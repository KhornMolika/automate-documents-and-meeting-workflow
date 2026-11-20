from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
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

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

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
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # Generative LLM provider: auto | gemini | ollama | opencode
    # auto uses Gemini when GEMINI_API_KEY is set, otherwise the local Ollama model.
    LLM_PROVIDER: str = "auto"
    AUTO_SUMMARIZE_ON_UPLOAD: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT_SECONDS: int = 300
    OPENCODE_BASE_URL: str = "https://opencode.ai/inference/openai/v1"
    OPENCODE_API_KEY: str = ""
    OPENCODE_MODEL: str = "gemini-3.8-flash"
    OPENCODE_SESSION: str = "aub-workflow"

    # Google Workspace OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = ""

    # File storage limits
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "xlsx", "csv"]

    # Local speech service
    SPEECH_SERVICE_URL: str = "http://localhost:8001"


settings = Settings()
