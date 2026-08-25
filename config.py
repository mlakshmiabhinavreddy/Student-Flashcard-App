"""
Application configuration.
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1" or os.getenv("FLASK_ENV") == "development"
    DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join("database", "flashcards.db"))
    
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        if DEBUG:
            SECRET_KEY = "dev-secret-change-in-production"
        else:
            raise RuntimeError("SECRET_KEY environment variable must be set in production.")
