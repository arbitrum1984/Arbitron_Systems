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
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Robustly find the .env file relative to this file
# this file is at: terminal/app/core/config.py
# we want: arbitron_terminal_full/.env
# path: ../../../.env from here
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Fallback to local .env if run from within terminal dir and user moved it
    load_dotenv(".env")


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

    # Integrations
    EDGAR_API_KEY: Optional[str] = None
    FRED_API_KEY: Optional[str] = None
    QUANT_SERVICE_URL: Optional[str] = "http://quant_engine:8001"

    RUN_BACKGROUND_TASKS: bool = False
    
    # Filesystem and model configuration
    MODEL_PATH: str = "data/model.pt"
    DB_PATH: str = "data/arbitron.sqlite"

    class Config:
        """Pydantic configuration."""
        # We manually loaded .env above, so we don't strictly need this,
        # but kept for standard behavior if env vars are set.
        pass


# Create a single `settings` instance for application-wide use.
settings = Settings()