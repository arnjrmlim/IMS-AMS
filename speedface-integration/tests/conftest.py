"""
conftest.py — Shared pytest fixtures for Phase 2 tests.

All tests use an in-memory SQLite database (:memory:) so they are:
  - Fast (no disk I/O)
  - Isolated (each test gets a fresh DB via the db_conn fixture)
  - Safe (never touch the real speedface.db or the physical device)

Device communication is mocked — no real SpeedFace-V5L or network needed.
"""

import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import app.database as db
from app.config import DeviceConfig
from app.sync_engine import SyncConfig


# ---------------------------------------------------------------------------
# In-memory database
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn():
    """
    Provide a fresh in-memory SQLite connection with full schema applied.
    Closed automatically after each test.
    """
    conn = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(db._DDL)
    conn.executescript(db._DDL_PHASE3)   # Phase 3 tables (device_employee_mapping)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    """
    Provide a temporary file-based database path for tests that need
    a real file (e.g. sync_engine integration tests).
    The file is automatically removed after the test session.
    """
    return str(tmp_path / "test_speedface.db")


# ---------------------------------------------------------------------------
# Device and config stubs
# ---------------------------------------------------------------------------

@pytest.fixture
def device_cfg():
    """A DeviceConfig-like object that never touches the real .env."""
    cfg = MagicMock(spec=DeviceConfig)
    cfg.ip       = '192.168.99.99'
    cfg.port     = 4370
    cfg.timeout  = 5
    cfg.comm_key = 0
    return cfg


@pytest.fixture
def sync_cfg(db_path):
    """SyncConfig pointing to the temporary test database."""
    return SyncConfig(
        dry_run    = False,
        batch_size = 100,
        max_retries= 1,
        retry_delays=[0],
        db_path    = db_path,
    )


@pytest.fixture
def dry_run_sync_cfg(db_path):
    """SyncConfig in dry-run mode."""
    return SyncConfig(
        dry_run     = True,
        batch_size  = 100,
        max_retries = 1,
        retry_delays= [0],
        db_path     = db_path,
    )


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------

def make_attendance_record(
    user_id='1001',
    dt='2026-08-13 08:00:00',
    status=0,
    punch=10,
):
    """Return a dict matching the structure returned by device.get_attendance()."""
    return {
        'user_id':      user_id,
        'timestamp':    datetime.strptime(dt, '%Y-%m-%d %H:%M:%S'),
        'status':       status,
        'status_label': 'Check In',
        'punch':        punch,
        'verify_type':  punch,
        'verify_label': 'Face',
    }


def make_user_record(uid=1, user_id='1001', name='Test User', privilege=0, card=0):
    """Return a dict matching the structure returned by device.get_users()."""
    return {
        'uid':             uid,
        'user_id':         user_id,
        'name':            name,
        'privilege':       privilege,
        'privilege_label': 'User',
        'card':            card,
    }


def make_device_info(
    device_name='SpeedFace-V5L',
    serial='TEST123',
    firmware='Ver 6.60 Aug 28 2020',
    platform='ZAM180_TFT',
    users=5,
    records=10,
):
    return {
        'device_name':      device_name,
        'serial_number':    serial,
        'firmware_version': firmware,
        'platform':         platform,
        'face_version':     '11',
        'fp_version':       '10',
        'mac':              'AA:BB:CC:DD:EE:FF',
        'device_time':      datetime(2026, 8, 13, 14, 30, 0),
        'users':            users,
        'fingers':          0,
        'records':          records,
        'users_cap':        50000,
        'fingers_cap':      3000,
    }


# ---------------------------------------------------------------------------
# Seeded device row helper
# ---------------------------------------------------------------------------

def seed_device(conn, ip='192.168.99.99', port=4370) -> int:
    """Insert a minimal device row and return its id."""
    from app.database import _now_utc
    now = _now_utc()
    cur = conn.execute(
        "INSERT INTO devices (ip_address, port, created_at, updated_at) VALUES (?,?,?,?)",
        (ip, port, now, now)
    )
    conn.commit()
    return cur.lastrowid
