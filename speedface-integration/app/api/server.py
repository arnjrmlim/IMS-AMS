"""
app/api/server.py — FastAPI application factory for Phase 3.

Creates the FastAPI app, registers routes, and configures middleware.

Usage:
    # Start via CLI:
    python run.py serve

    # Or directly:
    uvicorn app.api.server:app --host 127.0.0.1 --port 8000

DEVICE POLICY:
    The API server only serves data from the local SQLite database.
    It does not communicate directly with the SpeedFace device except
    through the sync trigger endpoint, which performs a read-only fetch.

SECURITY:
    - All endpoints except /api/health require Bearer authentication.
    - API key is loaded from the API_KEY environment variable.
    - Never hard-coded. Never logged.
    - The server binds to 127.0.0.1 by default (LAN access requires
      explicit API_HOST configuration).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
import app.database as db
from app.config.settings import get_db_path, get_settings_summary

logger = logging.getLogger(__name__)

_APP_DESCRIPTION = """
## SpeedFace-V5L Integration API — Phase 3

Read-only REST API providing access to attendance data synchronized from
the ZKTeco SpeedFace-V5L biometric device.

### Device Policy
The SpeedFace-V5L is **read-only**. This API serves synchronized local data.
No endpoint writes, modifies, or deletes data on the device.

### Authentication
All endpoints except `/api/health` require:
```
Authorization: Bearer <API_KEY>
```

### Data flow
```
SpeedFace-V5L → (read-only) → Python Sync Service → SQLite → This API → Laravel
```
"""


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Lifespan handler replacing deprecated on_event."""
    # Startup
    logger.info("API server starting up ...")
    try:
        db.init_db(get_db_path())
        logger.info("Database ready.")
    except Exception as exc:
        logger.error("Database init failed on startup: %s", exc)

    try:
        settings = get_settings_summary()
        logger.info(
            "API settings: host=%s port=%s sync_interval=%ds",
            settings['api_host'],
            settings['api_port'],
            settings['sync_interval_seconds'],
        )
    except Exception:
        pass
    logger.info("API server ready. Docs: /docs")

    yield  # application runs

    # Shutdown
    logger.info("API server shutting down.")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    Called by uvicorn when starting the server.
    """
    app = FastAPI(
        title       = 'SpeedFace-V5L Integration API',
        description = _APP_DESCRIPTION,
        version     = '3.0.0',
        docs_url    = '/docs',
        redoc_url   = '/redoc',
        openapi_url = '/openapi.json',
        lifespan    = _lifespan,
    )

    # ── Global exception handler ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Never expose tracebacks, paths, or credentials to API clients
        logger.error(
            "Unhandled exception on %s %s: %s",
            request.method, request.url.path, exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                'success': False,
                'error': {
                    'code':    'INTERNAL_SERVER_ERROR',
                    'message': 'An unexpected error occurred. Check server logs.',
                }
            }
        )

    # ── Register routes ──────────────────────────────────────────────────────
    app.include_router(router)

    return app


# Module-level app instance for uvicorn
app = create_app()
