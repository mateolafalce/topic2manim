import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
ENV_EXAMPLE_PATH = ENV_PATH.parent / ".env.example"


def ensure_env_file():
    """Create .env from .env.example when missing (first-run setup)."""
    if ENV_PATH.is_file():
        return False
    if not ENV_EXAMPLE_PATH.is_file():
        return False
    shutil.copy2(ENV_EXAMPLE_PATH, ENV_PATH)
    return True


def load_app_env():
    """Load project .env from a fixed path (works in Docker and local dev)."""
    ensure_env_file()
    if ENV_PATH.is_file():
        load_dotenv(dotenv_path=ENV_PATH, override=True)


def get_env(name, default=None):
    load_app_env()
    return os.getenv(name, default)
