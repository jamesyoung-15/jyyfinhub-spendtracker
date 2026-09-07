"""Application configuration via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Project configurations"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    log_level: LogLevel = Field(default="ERROR", description="Numeric log level")

    # fastapi configs
    app_project_name: str = Field(
        default="JYYFinHub Spend Tracker", description="FastAPI app name"
    )
    app_debug: bool = Field(default=False, description="Whether to run in debug mode")
    app_port: int = Field(default=5000, description="Port to run FastAPI application")
    app_host: str = Field(default="127.0.0.1", description="FastAPI host argument")

    # db configs
    postgres_host: str = Field(
        default="127.0.0.1", description="Postgres server hostname"
    )
    postgres_port: int = Field(default=5432, description="Postgres server port")
    postgres_username: str = Field(default="postgres", description="Postgres username")
    postgres_password: SecretStr = Field(..., description="Postgres user password")
    postgres_db: str = Field(default="spendtracker")

    # sqlalchemy configs
    sqlalchemy_max_overflow: int = Field(default=10)
    sqlalchemy_pool_size: int = Field(default=5)

    @computed_field
    @property
    def database_url(self) -> URL:
        """Generate SQLAlchemy database URL for Postgres from config"""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_username,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton configuration to read settings once only"""
    return Settings()  # type: ignore - postgres password is secretstr
