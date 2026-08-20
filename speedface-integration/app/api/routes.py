"""
app/api/routes.py — All REST API endpoint definitions for Phase 3.

Endpoints (all READ-ONLY with respect to the SpeedFace device):

  GET  /api/health                  — liveness check (no auth required)
  GET  /api/device                  — list all registered devices
  GET  /api/device/{id}             — single device details
  GET  /api/sync/status             — synchronisation status from local DB
  GET  /api/sync/history            — recent sync run history
  POST /api/sync                    — trigger a read-only device sync
  GET  /api/attendance              — paginated attendance records + filtering
  GET  /api/device-users            — paginated device users

Authentication:
  All endpoints except /api/health require:
    Authorization: Bearer <API_KEY>

Pagination:
  ?page=1&per_page=100   (default per_page=100, max 1000)

Filtering (attendance):
  ?device_id=1
  ?device_user_id=1001
  ?start_datetime=2026-08-01%2000:00:00
  ?end_datetime=2026-08-31%2023:59:59

DEVICE POLICY:
  This router never calls any device write operation.
  POST /api/sync only triggers a READ-ONLY fetch from the device.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.schemas import (
    AttendanceRecordSchema,
    DeviceSchema,
    DeviceUserSchema,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    Meta,
    MappingSchema,
    SuccessResponse,
    SyncRunSchema,
    SyncStatusSchema,
    SyncTriggerResponse,
)
import app.database as db
from app.config.settings import get_api_key_optional, get_db_path
from app.sync_service import SyncInProgressError, get_sync_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Security ──────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def _require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """
    Dependency: validate Bearer token against API_KEY env var.
    Returns normally on success; raises 401 on failure.
    Never logs the key value.
    """
    expected_key = get_api_key_optional()
    if not expected_key:
        # API_KEY not configured — reject all requests for safety
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                code='API_KEY_NOT_CONFIGURED',
                message='API_KEY is not set on the server. Configure it in .env.'
            ).model_dump(),
        )

    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetail(
                code='UNAUTHORIZED',
                message='Missing or invalid Authorization header. '
                        'Use: Authorization: Bearer <API_KEY>'
            ).model_dump(),
            headers={'WWW-Authenticate': 'Bearer'},
        )

    # Constant-time comparison to prevent timing attacks
    import hmac
    provided = credentials.credentials.encode()
    expected = expected_key.encode()
    if not hmac.compare_digest(provided, expected):
        logger.warning("API: authentication failed — invalid API key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetail(
                code='UNAUTHORIZED',
                message='Invalid API credentials.'
            ).model_dump(),
            headers={'WWW-Authenticate': 'Bearer'},
        )


def _get_db_conn():
    """FastAPI dependency: open a DB connection, yield it, close on teardown."""
    conn = db.get_connection(get_db_path())
    try:
        yield conn
    finally:
        conn.close()


def _validate_pagination(
    page: int, per_page: int, max_per_page: int = 1000
) -> tuple[int, int]:
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetail(code='INVALID_PARAM',
                               message='page must be >= 1').model_dump()
        )
    if per_page < 1 or per_page > max_per_page:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetail(
                code='INVALID_PARAM',
                message=f'per_page must be between 1 and {max_per_page}'
            ).model_dump()
        )
    return page, per_page


def _validate_datetime(value: Optional[str], name: str) -> Optional[str]:
    if value is None:
        return None
    try:
        datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return value
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetail(
                code='INVALID_PARAM',
                message=f"{name} must be in format 'YYYY-MM-DD HH:MM:SS', got '{value}'"
            ).model_dump()
        )


# ── Health ────────────────────────────────────────────────────────────────────

@router.get(
    '/api/health',
    response_model=HealthResponse,
    summary='Health check',
    tags=['health'],
)
def health():
    """
    Liveness check. No authentication required.
    Always returns 200 if the service is running.
    """
    return HealthResponse()


# ── Devices ───────────────────────────────────────────────────────────────────

@router.get(
    '/api/device',
    response_model=SuccessResponse,
    summary='List registered devices',
    tags=['devices'],
    dependencies=[Depends(_require_auth)],
)
def list_devices(conn=Depends(_get_db_conn)):
    """
    Return all registered SpeedFace devices from the local database.
    Does not connect to any device.
    """
    rows = db.get_all_devices(conn)
    devices = [dict(r) for r in rows]
    logger.info("API: GET /api/device — returned %d device(s)", len(devices))
    return SuccessResponse(data=devices)


@router.get(
    '/api/device/{device_id}',
    response_model=SuccessResponse,
    summary='Get single device',
    tags=['devices'],
    dependencies=[Depends(_require_auth)],
)
def get_device(device_id: int, conn=Depends(_get_db_conn)):
    row = db.get_device_by_id(conn, device_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetail(
                code='NOT_FOUND',
                message=f'Device id={device_id} not found'
            ).model_dump()
        )
    logger.info("API: GET /api/device/%d", device_id)
    return SuccessResponse(data=dict(row))


# ── Sync status ───────────────────────────────────────────────────────────────

@router.get(
    '/api/sync/status',
    response_model=SuccessResponse,
    summary='Synchronisation status',
    tags=['sync'],
    dependencies=[Depends(_require_auth)],
)
def sync_status_endpoint(conn=Depends(_get_db_conn)):
    """
    Return synchronisation status from the local database.
    Does NOT connect to the device.
    """
    from app.config import DeviceConfig
    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(
                code='CONFIG_ERROR',
                message=str(exc)
            ).model_dump()
        )

    service = get_sync_service(get_db_path())
    raw = service.get_status(cfg)

    last_run_data = None
    device_id_val = None
    if raw.get('device_found'):
        device_row = db.get_device_by_ip_port(conn, cfg.ip, cfg.port)
        if device_row:
            device_id_val = device_row['id']
            last_run = db.get_last_sync_run(conn, device_id_val)
            if last_run:
                last_run_data = SyncRunSchema(
                    id               = last_run['id'],
                    device_id        = last_run['device_id'],
                    started_at       = last_run['started_at'],
                    completed_at     = last_run['completed_at'],
                    status           = last_run['status'],
                    records_read     = last_run['records_read'] or 0,
                    records_inserted = last_run['records_inserted'] or 0,
                    records_skipped  = last_run['records_skipped'] or 0,
                    records_failed   = last_run['records_failed'] or 0,
                    error_message    = last_run['error_message'],
                    dry_run          = bool(last_run['dry_run']),
                )

    schema = SyncStatusSchema(
        device_found         = raw.get('device_found', False),
        device_ip            = cfg.ip,
        device_port          = cfg.port,
        device_name          = raw.get('device_name'),
        serial_number        = raw.get('serial_number'),
        firmware             = raw.get('firmware'),
        platform             = raw.get('platform'),
        local_record_count   = raw.get('local_record_count', 0),
        last_sync_at         = raw.get('last_sync_at'),
        last_sync_status     = raw.get('last_sync_status'),
        last_record_datetime = raw.get('last_record_datetime'),
        total_sync_runs      = raw.get('total_sync_runs', 0),
        sync_in_progress     = service.is_running(),
        last_run             = last_run_data,
    )
    logger.info("API: GET /api/sync/status")
    return SuccessResponse(data=schema.model_dump())


@router.get(
    '/api/sync/history',
    response_model=SuccessResponse,
    summary='Sync run history',
    tags=['sync'],
    dependencies=[Depends(_require_auth)],
)
def sync_history(
    limit: int = Query(default=10, ge=1, le=100),
    conn=Depends(_get_db_conn),
):
    """Return the most recent sync run records (excluding dry-runs)."""
    from app.config import DeviceConfig
    try:
        cfg = DeviceConfig()
    except ValueError:
        return SuccessResponse(data=[])

    device_row = db.get_device_by_ip_port(conn, cfg.ip, cfg.port)
    if not device_row:
        return SuccessResponse(data=[])

    rows = db.get_sync_run_history(conn, device_row['id'], limit=limit)
    history = [dict(r) for r in rows]
    logger.info("API: GET /api/sync/history — %d run(s)", len(history))
    return SuccessResponse(data=history)


# ── Sync trigger ──────────────────────────────────────────────────────────────

@router.post(
    '/api/sync',
    response_model=SuccessResponse,
    summary='Trigger attendance synchronisation',
    tags=['sync'],
    dependencies=[Depends(_require_auth)],
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_sync():
    """
    Trigger a READ-ONLY attendance fetch from the SpeedFace device.

    - Fetches attendance records from the device (read-only).
    - Stores new records in local SQLite (duplicate-safe).
    - Returns immediately with 202 Accepted.
    - If a sync is already running, returns 409 Conflict.

    DEVICE POLICY: This endpoint only reads from the device.
    No data is written, modified, or deleted on the SpeedFace.
    """
    from app.config import DeviceConfig
    import threading

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetail(code='CONFIG_ERROR', message=str(exc)).model_dump()
        )

    service = get_sync_service(get_db_path())

    if service.is_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorDetail(
                code='SYNC_IN_PROGRESS',
                message='A synchronisation is already running. '
                        'Wait for it to complete before starting another.'
            ).model_dump()
        )

    # Run sync in background thread so API returns immediately
    def _bg_sync():
        try:
            result = service.sync_attendance(cfg)
            logger.info(
                "API-triggered sync %s — inserted=%d skipped=%d",
                result.status, result.records_inserted, result.records_skipped
            )
        except SyncInProgressError:
            logger.warning("API-triggered sync: race condition — already running")
        except Exception as exc:
            logger.error("API-triggered sync error: %s", exc, exc_info=True)

    t = threading.Thread(target=_bg_sync, daemon=True, name='api-sync-trigger')
    t.start()

    logger.info("API: POST /api/sync — sync triggered in background")
    return SuccessResponse(
        data=SyncTriggerResponse(
            success=True,
            message='Synchronisation started. '
                    'Poll GET /api/sync/status to track progress.',
        ).model_dump()
    )


# ── Attendance ────────────────────────────────────────────────────────────────

@router.get(
    '/api/attendance',
    response_model=SuccessResponse,
    summary='List attendance records',
    tags=['attendance'],
    dependencies=[Depends(_require_auth)],
)
def list_attendance(
    device_id:      Optional[int] = Query(default=None),
    device_user_id: Optional[str] = Query(default=None),
    start_datetime: Optional[str] = Query(default=None),
    end_datetime:   Optional[str] = Query(default=None),
    page:           int           = Query(default=1,   ge=1),
    per_page:       int           = Query(default=100, ge=1, le=1000),
    conn=Depends(_get_db_conn),
):
    """
    Return paginated attendance records from the local database.

    Filters:
      device_id      — filter by device
      device_user_id — filter by device user ID
      start_datetime — ISO format 'YYYY-MM-DD HH:MM:SS'
      end_datetime   — ISO format 'YYYY-MM-DD HH:MM:SS'

    Pagination:
      page     (default 1)
      per_page (default 100, max 1000)

    IMPORTANT: This endpoint serves already-synchronized local data.
    It does NOT connect to the SpeedFace device.
    """
    _validate_pagination(page, per_page)
    start_dt = _validate_datetime(start_datetime, 'start_datetime')
    end_dt   = _validate_datetime(end_datetime,   'end_datetime')

    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetail(
                code='INVALID_PARAM',
                message='start_datetime must be before end_datetime'
            ).model_dump()
        )

    rows, total = db.get_attendance_page(
        conn,
        device_id      = device_id,
        device_user_id = device_user_id,
        start_datetime = start_dt,
        end_datetime   = end_dt,
        page           = page,
        per_page       = per_page,
    )

    records = [AttendanceRecordSchema.from_db_row(r).model_dump() for r in rows]
    meta    = Meta(page=page, per_page=per_page, total=total)

    logger.info(
        "API: GET /api/attendance — page=%d per_page=%d total=%d",
        page, per_page, total
    )
    return SuccessResponse(data=records, meta=meta)


# ── Device users ──────────────────────────────────────────────────────────────

@router.get(
    '/api/device-users',
    response_model=SuccessResponse,
    summary='List device users',
    tags=['device-users'],
    dependencies=[Depends(_require_auth)],
)
def list_device_users(
    device_id: Optional[int] = Query(default=None),
    page:      int           = Query(default=1,   ge=1),
    per_page:  int           = Query(default=100, ge=1, le=1000),
    conn=Depends(_get_db_conn),
):
    """
    Return paginated device user records from the local database.
    Does NOT connect to the device.
    Biometric templates are never returned.
    """
    _validate_pagination(page, per_page)

    rows, total = db.get_device_users_page(
        conn,
        device_id = device_id,
        page      = page,
        per_page  = per_page,
    )

    users = [DeviceUserSchema.from_db_row(r).model_dump() for r in rows]
    meta  = Meta(page=page, per_page=per_page, total=total)

    logger.info(
        "API: GET /api/device-users — page=%d per_page=%d total=%d",
        page, per_page, total
    )
    return SuccessResponse(data=users, meta=meta)
