"""
Application configuration.
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join("database", "flashcards.db"))
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
