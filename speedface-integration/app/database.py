"""
database.py — SQLite schema, migrations, and all database access for Phase 2.

Database location: data/speedface.db  (relative to project root)

Tables
------
  devices            — one row per registered SpeedFace device
  device_users       — users fetched from the device (read-only copy)
  attendance_records — attendance transactions fetched from the device
  sync_runs          — one row per synchronisation attempt
  sync_state         — current checkpoint per device

READ-ONLY DEVICE POLICY
-----------------------
This module reads data FROM the device and writes it INTO the local database.
It never writes anything back to the SpeedFace-V5L.

DUPLICATE PROTECTION
--------------------
attendance_records has a UNIQUE constraint on:
  (device_id, device_user_id, punch_datetime, punch_state, verify_type)

pyzk does not expose a stable per-record transaction ID for SpeedFace-V5L,
so this composite key is the deduplication strategy.  INSERT OR IGNORE is
used so concurrent or repeated syncs cannot produce duplicates.

Limitation: if the same employee punches twice in the same second with the
same state and verification type, only one record is stored.  In practice
this is extremely unlikely on a single access-control device.
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Project root is one level above this file
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, 'data', 'speedface.db')


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """
-- ── devices ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT,
    ip_address          TEXT    NOT NULL,
    port                INTEGER NOT NULL DEFAULT 4370,
    serial_number       TEXT,
    model               TEXT,
    firmware_version    TEXT,
    platform            TEXT,
    face_version        TEXT,
    fp_version          TEXT,
    mac_address         TEXT,
    user_count          INTEGER,
    attendance_count    INTEGER,
    last_connected_at   TEXT,
    last_sync_at        TEXT,
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL,
    UNIQUE (ip_address, port)
);

-- ── device_users ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS device_users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL REFERENCES devices(id),
    device_uid      INTEGER,
    device_user_id  TEXT    NOT NULL,
    name            TEXT,
    privilege       INTEGER DEFAULT 0,
    card_number     TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    UNIQUE (device_id, device_user_id)
);

-- ── attendance_records ────────────────────────────────────────────────────
-- Composite UNIQUE constraint is the primary duplicate guard.
-- INSERT OR IGNORE is used on every insert so repeated syncs are safe.
CREATE TABLE IF NOT EXISTS attendance_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           INTEGER NOT NULL REFERENCES devices(id),
    device_user_id      TEXT    NOT NULL,
    punch_datetime      TEXT    NOT NULL,
    punch_state         INTEGER NOT NULL DEFAULT 0,
    verification_type   INTEGER NOT NULL DEFAULT 0,
    raw_data            TEXT,
    created_at          TEXT    NOT NULL,
    UNIQUE (device_id, device_user_id, punch_datetime, punch_state, verification_type)
);

-- Index to speed up incremental-style queries (filter by datetime)
CREATE INDEX IF NOT EXISTS idx_att_device_datetime
    ON attendance_records (device_id, punch_datetime);

-- ── sync_runs ─────────────────────────────────────────────────────────────
-- status: 'running' | 'success' | 'partial' | 'failed'
CREATE TABLE IF NOT EXISTS sync_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           INTEGER NOT NULL REFERENCES devices(id),
    started_at          TEXT    NOT NULL,
    completed_at        TEXT,
    status              TEXT    NOT NULL DEFAULT 'running',
    records_read        INTEGER DEFAULT 0,
    records_inserted    INTEGER DEFAULT 0,
    records_skipped     INTEGER DEFAULT 0,
    records_failed      INTEGER DEFAULT 0,
    error_message       TEXT,
    dry_run             INTEGER NOT NULL DEFAULT 0   -- 1 = dry-run, no DB writes
);

-- ── sync_state ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sync_state (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id                   INTEGER NOT NULL UNIQUE REFERENCES devices(id),
    last_successful_sync_at     TEXT,
    last_device_record_datetime TEXT,
    last_sync_run_id            INTEGER REFERENCES sync_runs(id),
    updated_at                  TEXT    NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def _dt_to_str(dt) -> Optional[str]:
    """Convert a datetime (or string) to a sortable string, or None."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return str(dt)


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Open (or create) the SQLite database and return a connection.

    - WAL journal mode for better concurrent read performance.
    - Foreign key enforcement enabled.
    - Row factory set to sqlite3.Row for dict-like access.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Apply DDL: create all tables and indexes if they do not already exist.
    Safe to call on every application start — uses CREATE IF NOT EXISTS.
    """
    logger.info("Initialising database at %s", db_path)
    conn = get_connection(db_path)
    try:
        conn.executescript(_DDL)
        conn.commit()
        logger.info("Database schema ready.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# devices table
# ---------------------------------------------------------------------------

def upsert_device(conn: sqlite3.Connection, cfg, info: dict) -> int:
    """
    Insert or update a device record from DeviceConfig + device info dict.
    Returns the device row id.
    """
    now = _now_utc()
    existing = conn.execute(
        "SELECT id FROM devices WHERE ip_address=? AND port=?",
        (cfg.ip, cfg.port)
    ).fetchone()

    user_count       = info.get('users')
    attendance_count = info.get('records')
    # Convert 'Not available through this protocol' sentinel to NULL
    if not isinstance(user_count, int):
        user_count = None
    if not isinstance(attendance_count, int):
        attendance_count = None

    if existing:
        conn.execute("""
            UPDATE devices SET
                name             = COALESCE(?, name),
                serial_number    = COALESCE(?, serial_number),
                model            = COALESCE(?, model),
                firmware_version = COALESCE(?, firmware_version),
                platform         = COALESCE(?, platform),
                face_version     = COALESCE(?, face_version),
                fp_version       = COALESCE(?, fp_version),
                mac_address      = COALESCE(?, mac_address),
                user_count       = COALESCE(?, user_count),
                attendance_count = COALESCE(?, attendance_count),
                last_connected_at = ?,
                updated_at        = ?
            WHERE id = ?
        """, (
            info.get('device_name'),
            info.get('serial_number'),
            info.get('device_name'),
            info.get('firmware_version'),
            info.get('platform'),
            str(info.get('face_version', '')) or None,
            str(info.get('fp_version', '')) or None,
            info.get('mac'),
            user_count,
            attendance_count,
            now, now,
            existing['id'],
        ))
        logger.debug("Updated device id=%s", existing['id'])
        return existing['id']
    else:
        cur = conn.execute("""
            INSERT INTO devices
                (name, ip_address, port, serial_number, model,
                 firmware_version, platform, face_version, fp_version,
                 mac_address, user_count, attendance_count,
                 last_connected_at, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            info.get('device_name'),
            cfg.ip,
            cfg.port,
            info.get('serial_number'),
            info.get('device_name'),
            info.get('firmware_version'),
            info.get('platform'),
            str(info.get('face_version', '')) or None,
            str(info.get('fp_version', '')) or None,
            info.get('mac'),
            user_count,
            attendance_count,
            now, now, now,
        ))
        logger.debug("Inserted device id=%s", cur.lastrowid)
        return cur.lastrowid


def update_device_last_sync(conn: sqlite3.Connection, device_id: int) -> None:
    now = _now_utc()
    conn.execute(
        "UPDATE devices SET last_sync_at=?, updated_at=? WHERE id=?",
        (now, now, device_id)
    )


# ---------------------------------------------------------------------------
# device_users table
# ---------------------------------------------------------------------------

def upsert_users(conn: sqlite3.Connection, device_id: int, users: list) -> dict:
    """
    Insert new users or update existing ones.
    Returns counts: {'inserted': n, 'updated': n, 'unchanged': n}
    """
    counts = {'inserted': 0, 'updated': 0, 'unchanged': 0}
    now = _now_utc()

    for u in users:
        user_id_str = str(u['user_id'])
        card = str(u['card']) if u['card'] not in (0, None, 'N/A', '') else None

        existing = conn.execute(
            "SELECT id, name, privilege, card_number FROM device_users "
            "WHERE device_id=? AND device_user_id=?",
            (device_id, user_id_str)
        ).fetchone()

        if existing is None:
            conn.execute("""
                INSERT INTO device_users
                    (device_id, device_uid, device_user_id, name, privilege,
                     card_number, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (device_id, u['uid'], user_id_str, u['name'],
                  u['privilege'], card, now, now))
            counts['inserted'] += 1
        else:
            changed = (
                existing['name']        != u['name']   or
                existing['privilege']   != u['privilege'] or
                existing['card_number'] != card
            )
            if changed:
                conn.execute("""
                    UPDATE device_users
                    SET name=?, privilege=?, card_number=?,
                        device_uid=?, updated_at=?
                    WHERE id=?
                """, (u['name'], u['privilege'], card,
                      u['uid'], now, existing['id']))
                counts['updated'] += 1
            else:
                counts['unchanged'] += 1

    return counts


# ---------------------------------------------------------------------------
# attendance_records table
# ---------------------------------------------------------------------------

def insert_attendance_batch(
    conn: sqlite3.Connection,
    device_id: int,
    records: list,
    dry_run: bool = False,
) -> dict:
    """
    Insert a batch of attendance records using INSERT OR IGNORE (dedup).

    Returns {'inserted': n, 'skipped': n, 'failed': n}

    Each record dict must have:
      user_id, timestamp, status, punch (verify_type)

    dry_run=True: counts what would happen but makes no DB changes.
    """
    counts = {'inserted': 0, 'skipped': 0, 'failed': 0}
    if not records:
        return counts

    now = _now_utc()

    rows_to_insert = []
    for r in records:
        try:
            punch_dt  = _dt_to_str(r['timestamp'])
            user_id   = str(r['user_id'])
            state     = int(r.get('status', 0))
            verify    = int(r.get('verify_type', r.get('punch', 0)))
            raw       = (
                f"user_id={user_id},"
                f"dt={punch_dt},"
                f"state={state},"
                f"verify={verify}"
            )
            rows_to_insert.append((device_id, user_id, punch_dt, state, verify, raw, now))
        except Exception as exc:
            logger.warning("Failed to prepare record for insert: %s — %s", r, exc)
            counts['failed'] += 1

    if dry_run:
        # In dry-run mode: check which rows already exist without inserting
        for row in rows_to_insert:
            _, user_id, punch_dt, state, verify, _, _ = row
            exists = conn.execute(
                "SELECT 1 FROM attendance_records "
                "WHERE device_id=? AND device_user_id=? AND punch_datetime=? "
                "AND punch_state=? AND verification_type=?",
                (device_id, user_id, punch_dt, state, verify)
            ).fetchone()
            if exists:
                counts['skipped'] += 1
            else:
                counts['inserted'] += 1   # "would insert"
        return counts

    # Real insert path — use INSERT OR IGNORE for atomic dedup
    for row in rows_to_insert:
        try:
            cur = conn.execute("""
                INSERT OR IGNORE INTO attendance_records
                    (device_id, device_user_id, punch_datetime,
                     punch_state, verification_type, raw_data, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, row)
            if cur.rowcount == 1:
                counts['inserted'] += 1
            else:
                counts['skipped'] += 1
        except sqlite3.Error as exc:
            logger.error("DB error inserting attendance row: %s — %s", row, exc)
            counts['failed'] += 1

    return counts


def get_attendance_count(conn: sqlite3.Connection, device_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM attendance_records WHERE device_id=?",
        (device_id,)
    ).fetchone()
    return row[0] if row else 0


def get_latest_attendance_datetime(
    conn: sqlite3.Connection, device_id: int
) -> Optional[str]:
    """Return the punch_datetime of the most recent local record, or None."""
    row = conn.execute(
        "SELECT MAX(punch_datetime) FROM attendance_records WHERE device_id=?",
        (device_id,)
    ).fetchone()
    return row[0] if row and row[0] else None


# ---------------------------------------------------------------------------
# sync_runs table
# ---------------------------------------------------------------------------

def start_sync_run(
    conn: sqlite3.Connection,
    device_id: int,
    dry_run: bool = False,
) -> int:
    """Insert a new sync_run row with status='running'. Returns run id."""
    now = _now_utc()
    cur = conn.execute("""
        INSERT INTO sync_runs
            (device_id, started_at, status, dry_run)
        VALUES (?, ?, 'running', ?)
    """, (device_id, now, 1 if dry_run else 0))
    conn.commit()
    return cur.lastrowid


def finish_sync_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    records_read: int = 0,
    records_inserted: int = 0,
    records_skipped: int = 0,
    records_failed: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Update an existing sync_run row to its final state."""
    now = _now_utc()
    conn.execute("""
        UPDATE sync_runs SET
            completed_at      = ?,
            status            = ?,
            records_read      = ?,
            records_inserted  = ?,
            records_skipped   = ?,
            records_failed    = ?,
            error_message     = ?
        WHERE id = ?
    """, (now, status, records_read, records_inserted,
          records_skipped, records_failed, error_message, run_id))
    conn.commit()


def get_last_sync_run(
    conn: sqlite3.Connection, device_id: int
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sync_runs WHERE device_id=? ORDER BY id DESC LIMIT 1",
        (device_id,)
    ).fetchone()


def get_sync_run_history(
    conn: sqlite3.Connection, device_id: int, limit: int = 10
) -> list:
    return conn.execute(
        "SELECT * FROM sync_runs WHERE device_id=? AND dry_run=0 "
        "ORDER BY id DESC LIMIT ?",
        (device_id, limit)
    ).fetchall()


# ---------------------------------------------------------------------------
# sync_state table
# ---------------------------------------------------------------------------

def upsert_sync_state(
    conn: sqlite3.Connection,
    device_id: int,
    run_id: int,
    last_record_datetime: Optional[str] = None,
) -> None:
    """Update (or create) the sync checkpoint for this device."""
    now = _now_utc()
    existing = conn.execute(
        "SELECT id FROM sync_state WHERE device_id=?", (device_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE sync_state SET
                last_successful_sync_at     = ?,
                last_device_record_datetime = COALESCE(?, last_device_record_datetime),
                last_sync_run_id            = ?,
                updated_at                  = ?
            WHERE device_id = ?
        """, (now, last_record_datetime, run_id, now, device_id))
    else:
        conn.execute("""
            INSERT INTO sync_state
                (device_id, last_successful_sync_at,
                 last_device_record_datetime, last_sync_run_id, updated_at)
            VALUES (?,?,?,?,?)
        """, (device_id, now, last_record_datetime, run_id, now))


def get_sync_state(
    conn: sqlite3.Connection, device_id: int
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sync_state WHERE device_id=?", (device_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Status / reporting queries
# ---------------------------------------------------------------------------

def get_device_by_ip_port(
    conn: sqlite3.Connection, ip: str, port: int
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM devices WHERE ip_address=? AND port=?",
        (ip, port)
    ).fetchone()


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Additional schema and query helpers
# ═══════════════════════════════════════════════════════════════════════════

_DDL_PHASE3 = """
-- ── device_employee_mapping ───────────────────────────────────────────────
-- Maps device users to future application employees.
-- employee_id is NULL until the employee management system is implemented.
-- Unmapped users are RETAINED — attendance data is never discarded.
--
-- mapping_status values:
--   'unmapped'  — device user not yet linked to an employee
--   'mapped'    — device user linked to an employee
--   'ignored'   — device user explicitly excluded (e.g. test users)
CREATE TABLE IF NOT EXISTS device_employee_mapping (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL REFERENCES devices(id),
    device_user_id  TEXT    NOT NULL,
    employee_id     TEXT,                    -- NULL until employees are set up
    mapping_status  TEXT NOT NULL DEFAULT 'unmapped',
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (device_id, device_user_id)
);

CREATE INDEX IF NOT EXISTS idx_mapping_status
    ON device_employee_mapping (mapping_status);

CREATE INDEX IF NOT EXISTS idx_att_user_id
    ON attendance_records (device_id, device_user_id);
"""


def init_db_phase3(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Apply Phase 3 schema additions.
    Safe to call repeatedly — uses CREATE IF NOT EXISTS.
    Called automatically by init_db().
    """
    conn = get_connection(db_path)
    try:
        conn.executescript(_DDL_PHASE3)
        conn.commit()
        logger.debug("Phase 3 schema applied.")
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Apply ALL schema (Phase 2 + Phase 3).
    Overrides the Phase 2 version — safe, additive only.
    """
    logger.info("Initialising database at %s", db_path)
    conn = get_connection(db_path)
    try:
        conn.executescript(_DDL)
        conn.executescript(_DDL_PHASE3)
        conn.commit()
        logger.info("Database schema ready.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# device_employee_mapping helpers
# ---------------------------------------------------------------------------

def ensure_mapping_rows(
    conn: sqlite3.Connection, device_id: int, user_ids: list[str]
) -> int:
    """
    Ensure every device_user_id has a mapping row (default: unmapped).
    Inserts missing rows only — does not modify existing rows.
    Returns count of newly inserted rows.
    """
    now = _now_utc()
    inserted = 0
    for uid in user_ids:
        cur = conn.execute("""
            INSERT OR IGNORE INTO device_employee_mapping
                (device_id, device_user_id, mapping_status, created_at, updated_at)
            VALUES (?, ?, 'unmapped', ?, ?)
        """, (device_id, str(uid), now, now))
        inserted += cur.rowcount
    return inserted


def get_unmapped_users(
    conn: sqlite3.Connection, device_id: int
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM device_employee_mapping "
        "WHERE device_id=? AND mapping_status='unmapped' ORDER BY device_user_id",
        (device_id,)
    ).fetchall()


def get_mapping_summary(
    conn: sqlite3.Connection, device_id: int
) -> dict:
    rows = conn.execute(
        "SELECT mapping_status, COUNT(*) as cnt "
        "FROM device_employee_mapping WHERE device_id=? "
        "GROUP BY mapping_status",
        (device_id,)
    ).fetchall()
    return {r['mapping_status']: r['cnt'] for r in rows}


# ---------------------------------------------------------------------------
# Paginated attendance query (Phase 3 API)
# ---------------------------------------------------------------------------

def get_attendance_page(
    conn: sqlite3.Connection,
    device_id: Optional[int] = None,
    device_user_id: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    page: int = 1,
    per_page: int = 100,
) -> tuple[list[sqlite3.Row], int]:
    """
    Return a paginated, optionally filtered list of attendance records.

    Returns (rows, total_count).
    page is 1-indexed.
    """
    where  = []
    params = []

    if device_id is not None:
        where.append("device_id = ?")
        params.append(device_id)
    if device_user_id is not None:
        where.append("device_user_id = ?")
        params.append(str(device_user_id))
    if start_datetime is not None:
        where.append("punch_datetime >= ?")
        params.append(start_datetime)
    if end_datetime is not None:
        where.append("punch_datetime <= ?")
        params.append(end_datetime)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM attendance_records {where_clause}",
        params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM attendance_records {where_clause} "
        f"ORDER BY punch_datetime DESC, id DESC "
        f"LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    return rows, total


def get_device_users_page(
    conn: sqlite3.Connection,
    device_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 100,
) -> tuple[list[sqlite3.Row], int]:
    """Return a paginated list of device users."""
    where  = []
    params = []

    if device_id is not None:
        where.append("device_id = ?")
        params.append(device_id)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM device_users {where_clause}", params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM device_users {where_clause} "
        f"ORDER BY device_user_id ASC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    return rows, total


def get_all_devices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM devices ORDER BY id"
    ).fetchall()


def get_device_by_id(
    conn: sqlite3.Connection, device_id: int
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM devices WHERE id=?", (device_id,)
    ).fetchone()
