"""
app/sync_service.py — Phase 3 SyncService with concurrent sync lock.

Wraps the Phase 2 sync_engine functions with:
  1. A thread-safe lock preventing concurrent synchronisations.
  2. A clean service interface for the API layer.
  3. Background worker support (interval-based auto-sync).

READ-ONLY GUARANTEE
-------------------
SyncService only calls:
  run_sync()          — reads attendance from device, writes to local DB
  run_sync_users()    — reads users from device, writes to local DB
  run_refresh_device()— reads device info, writes to local DB

It never calls any pyzk write/delete/clear method.
The SpeedFace-V5L remains completely untouched.

SYNC LOCK
---------
A threading.Lock prevents two concurrent sync operations from running
simultaneously (e.g. from the API trigger + background worker at the same time).
If a sync is already running, the second caller receives a SyncInProgressError
immediately rather than waiting or starting a duplicate pull.
"""

import logging
import threading
import time
from typing import Optional

from app.config import DeviceConfig
from app.sync_engine import (
    SyncConfig,
    SyncResult,
    run_sync,
    run_sync_users,
    run_refresh_device,
    get_sync_status,
)
import app.database as db

logger = logging.getLogger(__name__)


class SyncInProgressError(Exception):
    """Raised when a sync is requested while one is already running."""


class SyncService:
    """
    Thread-safe synchronisation service for Phase 3.

    Usage:
        service = SyncService()
        result  = service.sync_attendance()    # blocks until done
        status  = service.get_status()         # always non-blocking
    """

    def __init__(self, db_path: Optional[str] = None):
        self._lock        = threading.Lock()
        self._db_path     = db_path or db.DEFAULT_DB_PATH
        self._last_result: Optional[SyncResult] = None

    # ── Sync lock helpers ────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """True if a sync is currently in progress (non-blocking check)."""
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._lock.release()
            return False
        return True

    def _require_not_running(self) -> None:
        """Raise SyncInProgressError if a sync is already running."""
        if not self._lock.acquire(blocking=False):
            raise SyncInProgressError(
                "A synchronisation is already running. "
                "Wait for it to complete before starting another."
            )
        # We now hold the lock — caller must release via finally block

    # ── Public API ───────────────────────────────────────────────────────────

    def sync_attendance(
        self,
        device_cfg: DeviceConfig,
        dry_run: bool = False,
        batch_size: int = 1000,
        max_retries: int = 3,
    ) -> SyncResult:
        """
        Fetch attendance from the device and store locally.

        Raises:
            SyncInProgressError: if another sync is already running.

        Returns:
            SyncResult with full statistics.

        READ-ONLY on device.
        """
        self._require_not_running()
        try:
            logger.info(
                "SyncService: starting attendance sync%s",
                " (DRY RUN)" if dry_run else ""
            )
            sync_cfg = SyncConfig(
                dry_run     = dry_run,
                batch_size  = batch_size,
                max_retries = max_retries,
                db_path     = self._db_path,
            )
            result = run_sync(device_cfg, sync_cfg)
            self._last_result = result
            logger.info(
                "SyncService: attendance sync %s — inserted=%d skipped=%d",
                result.status, result.records_inserted, result.records_skipped
            )
            return result
        finally:
            self._lock.release()

    def sync_users(self, device_cfg: DeviceConfig) -> dict:
        """
        Fetch users from device and update local device_users table.
        READ-ONLY on device.
        """
        self._require_not_running()
        try:
            logger.info("SyncService: starting user sync")
            sync_cfg = SyncConfig(db_path=self._db_path)
            result = run_sync_users(device_cfg, sync_cfg)
            logger.info(
                "SyncService: user sync %s — inserted=%d updated=%d",
                result.get('status'), result.get('inserted'), result.get('updated')
            )
            return result
        finally:
            self._lock.release()

    def refresh_device(self, device_cfg: DeviceConfig) -> dict:
        """
        Re-read device metadata and update local devices table.
        READ-ONLY on device.
        """
        self._require_not_running()
        try:
            logger.info("SyncService: refreshing device info")
            sync_cfg = SyncConfig(db_path=self._db_path)
            result = run_refresh_device(device_cfg, sync_cfg)
            return result
        finally:
            self._lock.release()

    def get_status(self, device_cfg: DeviceConfig) -> dict:
        """
        Return sync status from local DB. Non-blocking, no device connection.
        """
        return get_sync_status(device_cfg, self._db_path)

    def get_last_result(self) -> Optional[SyncResult]:
        """Return the most recent SyncResult, or None if no sync has run."""
        return self._last_result


# ── Background worker ─────────────────────────────────────────────────────────

class SyncWorker:
    """
    Background sync worker using APScheduler.

    Runs sync_attendance() on a configurable interval.
    Designed to run as a separate process via:
        python run.py worker

    The worker never modifies the device.
    """

    def __init__(
        self,
        service: SyncService,
        device_cfg: DeviceConfig,
        interval_seconds: int = 300,
    ):
        self._service          = service
        self._device_cfg       = device_cfg
        self._interval_seconds = interval_seconds
        self._scheduler        = None
        self._stop_event       = threading.Event()

    def start(self) -> None:
        """Start the scheduler. Blocks until stop() is called."""
        from apscheduler.schedulers.blocking import BlockingScheduler

        logger.info(
            "SyncWorker: starting — interval=%ds device=%s:%s",
            self._interval_seconds,
            self._device_cfg.ip,
            self._device_cfg.port,
        )

        self._scheduler = BlockingScheduler(timezone='UTC')
        self._scheduler.add_job(
            self._run_sync_job,
            trigger='interval',
            seconds=self._interval_seconds,
            id='attendance_sync',
            max_instances=1,
            replace_existing=True,
            next_run_time=__import__('datetime').datetime.utcnow(),  # run immediately on start
        )

        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("SyncWorker: received stop signal")
        finally:
            self._scheduler.shutdown(wait=False)
            logger.info("SyncWorker: stopped")

    def stop(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def _run_sync_job(self) -> None:
        """Called by APScheduler on each interval tick."""
        logger.info("SyncWorker: scheduled sync starting ...")
        try:
            result = self._service.sync_attendance(self._device_cfg)
            logger.info(
                "SyncWorker: sync %s — read=%d inserted=%d skipped=%d duration=%.1fs",
                result.status,
                result.records_read,
                result.records_inserted,
                result.records_skipped,
                result.duration_s,
            )
        except SyncInProgressError:
            logger.warning("SyncWorker: sync skipped — another sync is already running")
        except Exception as exc:
            logger.error("SyncWorker: unhandled error in sync job: %s", exc, exc_info=True)


# ── Module-level singleton ────────────────────────────────────────────────────
# The API server imports this singleton so all requests share one lock.

_default_service: Optional[SyncService] = None


def get_sync_service(db_path: Optional[str] = None) -> SyncService:
    """
    Return the module-level SyncService singleton.
    Creates it on first call.
    """
    global _default_service
    if _default_service is None:
        _default_service = SyncService(db_path=db_path)
    return _default_service
