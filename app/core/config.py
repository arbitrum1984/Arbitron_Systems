"""Application configuration and environment settings.

This module defines a `Settings` data container powered by Pydantic
(`pydantic_settings.BaseSettings`). Configuration values are loaded
from environment variables and an optional `.env` file. The
`settings` instance provides a canonical, application-wide source
for values such as API keys, filesystem paths, and application
metadata used throughout the codebase.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the Arbitron Systems application.

    Attributes:
        PROJECT_NAME (str): Human-readable project name.
        VERSION (str): Application semantic version string.
        GEMINI_API_KEY (str): API key for the Gemini model provider.
            This field is expected to be present in the environment or
            in the `.env` file; code that requires the key should
            validate its presence at startup.
        MODEL_PATH (str): Filesystem path pointing to an optional
            local model artifact.
        DB_PATH (str): Filesystem path used for the SQLite database.
    """

    PROJECT_NAME: str = "Arbitron Systems"
    VERSION: str = "2.0"

    # The environment loader provided by pydantic_settings will
    # automatically populate this field from an environment variable
    # named GEMINI_API_KEY or from an `.env` file.
    GEMINI_API_KEY: str

    APIFY_API_KEY: Optional[str] = None
    SERPAPI_API_KEY: Optional[str] = None
    RSS_FEEDS: Optional[str] = ""

    RUN_BACKGROUND_TASKS: bool = False
    
    # Filesystem and model configuration
    MODEL_PATH: str = "data/model.pt"
    DB_PATH: str = "data/arbitron.sqlite"

    class Config:
        """Pydantic configuration for environment loading.

        The `env_file` attribute instructs Pydantic to also read
        values from a `.env` file located at the project root when
        constructing `Settings`.
        """

        env_file = ".env"


# Create a single `settings` instance for application-wide use.
settings = Settings()