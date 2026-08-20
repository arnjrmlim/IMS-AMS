"""
test_database.py — Unit tests for app/database.py

Tests cover:
  - Schema creation (all tables exist)
  - Device upsert (insert + update)
  - User upsert (insert / update / unchanged)
  - Attendance insert with duplicate protection (INSERT OR IGNORE)
  - Batch insert counts (inserted / skipped / failed)
  - Dry-run batch (counts but no DB writes)
  - sync_runs insert / finish / query
  - sync_state upsert
  - Helper queries (get_attendance_count, get_latest_attendance_datetime)
"""

import sqlite3
from datetime import datetime

import pytest

import app.database as db
from tests.conftest import (
    make_attendance_record,
    make_user_record,
    make_device_info,
    seed_device,
)


# ── Schema ───────────────────────────────────────────────────────────────────

class TestSchema:
    def test_all_tables_exist(self, db_conn):
        tables = {
            row[0] for row in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for expected in ('devices', 'device_users', 'attendance_records',
                         'sync_runs', 'sync_state'):
            assert expected in tables, f"Table '{expected}' missing from schema"

    def test_attendance_unique_index_exists(self, db_conn):
        indexes = {
            row[0] for row in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert 'idx_att_device_datetime' in indexes

    def test_attendance_unique_constraint_enforced(self, db_conn):
        """Inserting identical rows must raise IntegrityError."""
        device_id = seed_device(db_conn)
        now = db._now_utc()
        row = (device_id, '1001', '2026-08-13 08:00:00', 0, 10, 'raw', now)
        sql = ("INSERT INTO attendance_records "
               "(device_id, device_user_id, punch_datetime, punch_state, "
               "verification_type, raw_data, created_at) VALUES (?,?,?,?,?,?,?)")
        db_conn.execute(sql, row)
        db_conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(sql, row)


# ── Device upsert ─────────────────────────────────────────────────────────────

class TestUpsertDevice:
    def test_insert_new_device(self, db_conn, device_cfg):
        info = make_device_info()
        device_id = db.upsert_device(db_conn, device_cfg, info)
        db_conn.commit()
        assert device_id > 0
        row = db_conn.execute(
            "SELECT * FROM devices WHERE id=?", (device_id,)
        ).fetchone()
        assert row['ip_address']       == device_cfg.ip
        assert row['port']             == device_cfg.port
        assert row['serial_number']    == 'TEST123'
        assert row['firmware_version'] == 'Ver 6.60 Aug 28 2020'
        assert row['platform']         == 'ZAM180_TFT'
        assert row['user_count']       == 5
        assert row['attendance_count'] == 10

    def test_upsert_updates_existing_device(self, db_conn, device_cfg):
        info1 = make_device_info(users=5, records=10)
        device_id = db.upsert_device(db_conn, device_cfg, info1)
        db_conn.commit()

        info2 = make_device_info(users=6, records=20, firmware='Ver 6.61 Jan 1 2025')
        device_id2 = db.upsert_device(db_conn, device_cfg, info2)
        db_conn.commit()

        assert device_id == device_id2, "Should update, not insert a second row"
        row = db_conn.execute(
            "SELECT * FROM devices WHERE id=?", (device_id,)
        ).fetchone()
        assert row['user_count']       == 6
        assert row['attendance_count'] == 20
        assert row['firmware_version'] == 'Ver 6.61 Jan 1 2025'

    def test_not_available_sentinel_stored_as_null(self, db_conn, device_cfg):
        info = make_device_info()
        info['users']   = 'Not available through this protocol'
        info['records'] = 'Not available through this protocol'
        device_id = db.upsert_device(db_conn, device_cfg, info)
        db_conn.commit()
        row = db_conn.execute(
            "SELECT user_count, attendance_count FROM devices WHERE id=?",
            (device_id,)
        ).fetchone()
        assert row['user_count']       is None
        assert row['attendance_count'] is None


# ── User upsert ───────────────────────────────────────────────────────────────

class TestUpsertUsers:
    def test_insert_new_users(self, db_conn):
        device_id = seed_device(db_conn)
        users = [
            make_user_record(uid=1, user_id='1001', name='Alice'),
            make_user_record(uid=2, user_id='1002', name='Bob'),
        ]
        counts = db.upsert_users(db_conn, device_id, users)
        db_conn.commit()
        assert counts['inserted']  == 2
        assert counts['updated']   == 0
        assert counts['unchanged'] == 0

        rows = db_conn.execute(
            "SELECT * FROM device_users WHERE device_id=? ORDER BY device_user_id",
            (device_id,)
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]['name'] == 'Alice'
        assert rows[1]['name'] == 'Bob'

    def test_update_changed_user(self, db_conn):
        device_id = seed_device(db_conn)
        users = [make_user_record(uid=1, user_id='1001', name='Alice')]
        db.upsert_users(db_conn, device_id, users)
        db_conn.commit()

        # Name changed on device
        users_updated = [make_user_record(uid=1, user_id='1001', name='Alice Updated')]
        counts = db.upsert_users(db_conn, device_id, users_updated)
        db_conn.commit()

        assert counts['updated']   == 1
        assert counts['inserted']  == 0
        assert counts['unchanged'] == 0
        row = db_conn.execute(
            "SELECT name FROM device_users WHERE device_id=? AND device_user_id='1001'",
            (device_id,)
        ).fetchone()
        assert row['name'] == 'Alice Updated'

    def test_unchanged_user_not_counted_as_update(self, db_conn):
        device_id = seed_device(db_conn)
        users = [make_user_record(uid=1, user_id='1001', name='Alice')]
        db.upsert_users(db_conn, device_id, users)
        db_conn.commit()

        # Same data again
        counts = db.upsert_users(db_conn, device_id, users)
        assert counts['unchanged'] == 1
        assert counts['updated']   == 0
        assert counts['inserted']  == 0

    def test_new_user_added_on_second_call(self, db_conn):
        device_id = seed_device(db_conn)
        db.upsert_users(db_conn, device_id,
                        [make_user_record(uid=1, user_id='1001', name='Alice')])
        db_conn.commit()

        counts = db.upsert_users(db_conn, device_id, [
            make_user_record(uid=1, user_id='1001', name='Alice'),
            make_user_record(uid=2, user_id='1002', name='Bob'),
        ])
        db_conn.commit()
        assert counts['inserted']  == 1
        assert counts['unchanged'] == 1


# ── Attendance batch insert ───────────────────────────────────────────────────

class TestInsertAttendanceBatch:
    def test_insert_new_records(self, db_conn):
        device_id = seed_device(db_conn)
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10),
            make_attendance_record('1001', '2026-08-13 17:00:00', 1, 10),
            make_attendance_record('1002', '2026-08-13 08:05:00', 0, 10),
        ]
        counts = db.insert_attendance_batch(db_conn, device_id, records)
        db_conn.commit()

        assert counts['inserted'] == 3
        assert counts['skipped']  == 0
        assert counts['failed']   == 0
        assert db.get_attendance_count(db_conn, device_id) == 3

    def test_duplicate_records_are_skipped(self, db_conn):
        """
        CORE DUPLICATE TEST — same records inserted twice.
        Only one local record must exist after both inserts.
        """
        device_id = seed_device(db_conn)
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10),
            make_attendance_record('1002', '2026-08-13 08:05:00', 0, 10),
        ]

        # First insert
        c1 = db.insert_attendance_batch(db_conn, device_id, records)
        db_conn.commit()
        assert c1['inserted'] == 2
        assert c1['skipped']  == 0

        # Second insert — same records
        c2 = db.insert_attendance_batch(db_conn, device_id, records)
        db_conn.commit()
        assert c2['inserted'] == 0
        assert c2['skipped']  == 2

        # DB must still have exactly 2 rows
        assert db.get_attendance_count(db_conn, device_id) == 2

    def test_partial_duplicates(self, db_conn):
        """2 existing + 1 new → inserted=1, skipped=2."""
        device_id = seed_device(db_conn)
        existing = [
            make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10),
            make_attendance_record('1002', '2026-08-13 08:05:00', 0, 10),
        ]
        db.insert_attendance_batch(db_conn, device_id, existing)
        db_conn.commit()

        combined = existing + [
            make_attendance_record('1003', '2026-08-13 08:10:00', 0, 10),
        ]
        counts = db.insert_attendance_batch(db_conn, device_id, combined)
        db_conn.commit()
        assert counts['inserted'] == 1
        assert counts['skipped']  == 2
        assert db.get_attendance_count(db_conn, device_id) == 3

    def test_empty_batch_returns_zero_counts(self, db_conn):
        device_id = seed_device(db_conn)
        counts = db.insert_attendance_batch(db_conn, device_id, [])
        assert counts == {'inserted': 0, 'skipped': 0, 'failed': 0}

    def test_different_state_same_datetime_is_unique_record(self, db_conn):
        """Same user/datetime but different punch_state → two distinct rows."""
        device_id = seed_device(db_conn)
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00', status=0, punch=10),
            make_attendance_record('1001', '2026-08-13 08:00:00', status=1, punch=10),
        ]
        counts = db.insert_attendance_batch(db_conn, device_id, records)
        db_conn.commit()
        assert counts['inserted'] == 2
        assert db.get_attendance_count(db_conn, device_id) == 2


# ── Dry-run batch ─────────────────────────────────────────────────────────────

class TestDryRunBatch:
    def test_dry_run_does_not_write_to_db(self, db_conn):
        """
        DRY-RUN TEST — batch insert in dry-run mode must not change the DB.
        """
        device_id = seed_device(db_conn)
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 08:05:00'),
        ]

        counts = db.insert_attendance_batch(db_conn, device_id, records, dry_run=True)
        # dry_run=True: counts['inserted'] means "would insert"
        assert counts['inserted'] == 2
        assert counts['skipped']  == 0

        # DB must be empty — no writes in dry-run
        assert db.get_attendance_count(db_conn, device_id) == 0

    def test_dry_run_counts_existing_as_skipped(self, db_conn):
        """After a real insert, dry-run of same records reports all as skipped."""
        device_id = seed_device(db_conn)
        records = [make_attendance_record('1001', '2026-08-13 08:00:00')]

        # Real insert
        db.insert_attendance_batch(db_conn, device_id, records, dry_run=False)
        db_conn.commit()

        # Dry-run of same records
        counts = db.insert_attendance_batch(db_conn, device_id, records, dry_run=True)
        assert counts['skipped']  == 1
        assert counts['inserted'] == 0

        # DB count unchanged
        assert db.get_attendance_count(db_conn, device_id) == 1


# ── sync_runs ─────────────────────────────────────────────────────────────────

class TestSyncRuns:
    def test_start_and_finish_run(self, db_conn):
        device_id = seed_device(db_conn)
        run_id = db.start_sync_run(db_conn, device_id)
        assert run_id > 0

        row = db_conn.execute(
            "SELECT * FROM sync_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row['status']   == 'running'
        assert row['dry_run']  == 0

        db.finish_sync_run(
            db_conn, run_id, 'success',
            records_read=100, records_inserted=95,
            records_skipped=5, records_failed=0,
        )
        row = db_conn.execute(
            "SELECT * FROM sync_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row['status']            == 'success'
        assert row['records_read']      == 100
        assert row['records_inserted']  == 95
        assert row['records_skipped']   == 5
        assert row['completed_at']      is not None

    def test_failed_run_stores_error_message(self, db_conn):
        device_id = seed_device(db_conn)
        run_id = db.start_sync_run(db_conn, device_id)
        db.finish_sync_run(
            db_conn, run_id, 'failed',
            error_message='Connection timed out'
        )
        row = db_conn.execute(
            "SELECT * FROM sync_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row['status']        == 'failed'
        assert row['error_message'] == 'Connection timed out'

    def test_dry_run_flag_stored(self, db_conn):
        device_id = seed_device(db_conn)
        run_id = db.start_sync_run(db_conn, device_id, dry_run=True)
        row = db_conn.execute(
            "SELECT dry_run FROM sync_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row['dry_run'] == 1


# ── sync_state ────────────────────────────────────────────────────────────────

class TestSyncState:
    def test_upsert_creates_state(self, db_conn):
        device_id = seed_device(db_conn)
        run_id    = db.start_sync_run(db_conn, device_id)
        db.upsert_sync_state(
            db_conn, device_id, run_id,
            last_record_datetime='2026-08-13 17:00:00'
        )
        db_conn.commit()

        state = db.get_sync_state(db_conn, device_id)
        assert state is not None
        assert state['last_sync_run_id']            == run_id
        assert state['last_device_record_datetime'] == '2026-08-13 17:00:00'

    def test_upsert_updates_existing_state(self, db_conn):
        device_id = seed_device(db_conn)
        run1 = db.start_sync_run(db_conn, device_id)
        db.upsert_sync_state(db_conn, device_id, run1, '2026-08-13 08:00:00')
        db_conn.commit()

        run2 = db.start_sync_run(db_conn, device_id)
        db.upsert_sync_state(db_conn, device_id, run2, '2026-08-13 17:00:00')
        db_conn.commit()

        state = db.get_sync_state(db_conn, device_id)
        assert state['last_sync_run_id']            == run2
        assert state['last_device_record_datetime'] == '2026-08-13 17:00:00'

        # Only one state row per device
        count = db_conn.execute(
            "SELECT COUNT(*) FROM sync_state WHERE device_id=?", (device_id,)
        ).fetchone()[0]
        assert count == 1


# ── Helper queries ────────────────────────────────────────────────────────────

class TestHelperQueries:
    def test_get_attendance_count(self, db_conn):
        device_id = seed_device(db_conn)
        assert db.get_attendance_count(db_conn, device_id) == 0

        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 08:05:00'),
        ]
        db.insert_attendance_batch(db_conn, device_id, records)
        db_conn.commit()
        assert db.get_attendance_count(db_conn, device_id) == 2

    def test_get_latest_attendance_datetime(self, db_conn):
        device_id = seed_device(db_conn)
        assert db.get_latest_attendance_datetime(db_conn, device_id) is None

        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1001', '2026-08-13 17:00:00'),
            make_attendance_record('1002', '2026-08-12 08:00:00'),
        ]
        db.insert_attendance_batch(db_conn, device_id, records)
        db_conn.commit()

        latest = db.get_latest_attendance_datetime(db_conn, device_id)
        assert latest == '2026-08-13 17:00:00'
