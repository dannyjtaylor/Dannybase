import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    # Authentication
    # These are the master credentials. They can be overridden in the .env file.
    AUTH_USERNAME: str = Field("valorantplayer25", env="AUTH_USERNAME")
    AUTH_PASSWORD: str = Field("admin", env="AUTH_PASSWORD")

    # JWT Settings
    # Generate a secure secret key with: openssl rand -hex 32
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 # Token expires in 1 hour

settings = Settings()