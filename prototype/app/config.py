"""
Application configuration.
All settings are loaded from env variables with defaults.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent          # prototype/
APP_DIR = BASE_DIR / "app"
DATA_DIR = APP_DIR / "data"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
SLOTS_FILE = DATA_DIR / "slots.json"
BOOKINGS_FILE = BASE_DIR / "bookings_log.json"
LOG_FILE = BASE_DIR / "call_log.txt"

# LLM
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_MAX_TOOL_ROUNDS: int = int(os.getenv("LLM_MAX_TOOL_ROUNDS", "5"))

# Session
SESSION_TIMEOUT_SECONDS: int = int(os.getenv("SESSION_TIMEOUT", "400"))  # 5 min
SESSION_WARNING_SECONDS: int = int(os.getenv("SESSION_WARNING", "240"))  # 3 min (warn)

# Server
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
