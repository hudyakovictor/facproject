from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "deeputin-api"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:4177", "http://127.0.0.1:4177"]

    class Config:
        env_file = ".env"


settings = Settings()