"""
Configuration and environment settings.

Load from .env or environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "claude" or "gemini"
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-20250514")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Weaviate Configuration
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", None)
WEAVIATE_EMBEDDED = os.getenv("WEAVIATE_EMBEDDED", "true").lower() == "true"

# Game Configuration
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "Opponent")
DEFAULT_DIFFICULTY = os.getenv("DEFAULT_DIFFICULTY", "intermediate")

# Scheduler Configuration
IDLE_CHECK_INTERVAL = int(os.getenv("IDLE_CHECK_INTERVAL", "10"))  # seconds
MAX_IDLE_TIME = int(os.getenv("MAX_IDLE_TIME", "60"))  # seconds before agent comments

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
