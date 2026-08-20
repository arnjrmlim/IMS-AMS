"""
app/config/settings.py — Unified application settings for Phase 3.

Loads ALL configuration from environment variables / .env file.
Nothing is hard-coded. Sensitive values (API key, comm key) are never logged.

Environment variables:
  Phase 1/2 (device):
    DEVICE_IP, DEVICE_PORT, DEVICE_COMM_KEY, DEVICE_TIMEOUT

  Phase 3 (API + worker):
    API_HOST            Host to bind the API server (default: 127.0.0.1)
    API_PORT            Port for the API server (default: 8000)
    API_KEY             Bearer token for API authentication (required for serve)
    API_RELOAD          Enable uvicorn auto-reload in dev mode (default: false)
    SYNC_INTERVAL_SECONDS  Background worker sync interval (default: 300)
    DB_PATH             Override default SQLite path (optional)
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(
    os.path.dirname(__file__), '..', '..', '.env'
))

logger = logging.getLogger(__name__)

# ── Project root ─────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Database ──────────────────────────────────────────────────────────────────
def get_db_path() -> str:
    override = os.getenv('DB_PATH', '').strip()
    if override:
        return override
    return os.path.join(PROJECT_ROOT, 'data', 'speedface.db')


# ── API server ────────────────────────────────────────────────────────────────
def get_api_host() -> str:
    return os.getenv('API_HOST', '127.0.0.1').strip()


def get_api_port() -> int:
    raw = os.getenv('API_PORT', '8000').strip()
    try:
        port = int(raw)
        if not (1 <= port <= 65535):
            raise ValueError(f"API_PORT {port} out of range")
        return port
    except (ValueError, TypeError):
        raise ValueError(f"API_PORT must be an integer, got '{raw}'")


def get_api_reload() -> bool:
    return os.getenv('API_RELOAD', 'false').strip().lower() in ('1', 'true', 'yes')


def get_api_key() -> str:
    """
    Return the API key used to authenticate requests.
    Raises ValueError if not set (required when serving).
    NEVER logged.
    """
    key = os.getenv('API_KEY', '').strip()
    if not key:
        raise ValueError(
            "API_KEY is not set. "
            "Add API_KEY=<secret> to your .env file before starting the API server."
        )
    return key


def get_api_key_optional() -> str | None:
    """Return the API key or None — used in contexts where serving is optional."""
    return os.getenv('API_KEY', '').strip() or None


# ── Sync worker ───────────────────────────────────────────────────────────────
def get_sync_interval() -> int:
    raw = os.getenv('SYNC_INTERVAL_SECONDS', '300').strip()
    try:
        interval = int(raw)
        if interval < 10:
            raise ValueError("SYNC_INTERVAL_SECONDS must be at least 10 seconds")
        return interval
    except (ValueError, TypeError):
        raise ValueError(f"SYNC_INTERVAL_SECONDS must be an integer, got '{raw}'")


# ── Convenience summary (safe — no secrets) ───────────────────────────────────
def get_settings_summary() -> dict:
    """Return a loggable settings summary. API key is never included."""
    return {
        'api_host':             get_api_host(),
        'api_port':             get_api_port(),
        'api_reload':           get_api_reload(),
        'api_key_set':          bool(get_api_key_optional()),
        'sync_interval_seconds': get_sync_interval(),
        'db_path':              get_db_path(),
    }
