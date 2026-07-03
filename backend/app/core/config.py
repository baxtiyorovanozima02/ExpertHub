from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    PRIMARY_LLM: str = "openai"

    TELEGRAM_BOT_TOKEN: str = ""


    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "experthub-files"
    MINIO_SECURE: bool = False

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "expert_documents"

    YANDEX_API_KEY: str = ""
    YANDEX_FOLDER_ID: str = ""


    YANDEX_STT_LANG: str = "uz-UZ"
    YANDEX_TTS_LANG: str = "uz-UZ"
    YANDEX_TTS_VOICE: str = "madi"


    HYBRID_SEARCH_ENABLED: bool = True

    class Config:
        env_file = ".env"


settings = Settings()