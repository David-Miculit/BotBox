from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    secret_key: str
    sqlite_database_url: str = "chatbox.db"
    pg_database_url: str | None = None
    voyage_api_key: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
