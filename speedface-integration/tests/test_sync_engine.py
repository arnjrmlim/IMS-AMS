"""
test_sync_engine.py — Integration tests for app/sync_engine.py

All tests mock SpeedFaceDevice so no real device or network is needed.
Each test uses a temporary file-based SQLite DB (via db_path fixture).

Test coverage:
  - Successful full sync: records inserted, sync_run recorded, sync_state set
  - Duplicate protection: second sync inserts 0 new records
  - Incremental simulation: new records on "device" after initial sync
  - Dry-run: no DB writes, no device changes
  - Connection failure + retry behaviour
  - Partial failure: batch DB error leaves previously committed data intact
  - User sync: insert + update + unchanged
  - Refresh device: device info stored locally
  - Device safety: attendance/user counts unchanged after sync
  - Sync status query (DB-only, no device connection)
  - Data integrity verification helper
"""

from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

import app.database as db
from app.device import DeviceConnectionError, DeviceReadError
from app.sync_engine import (
    SyncConfig,
    SyncResult,
    run_sync,
    run_sync_users,
    run_refresh_device,
    get_sync_status,
    verify_integrity,
)
from tests.conftest import (
    make_attendance_record,
    make_user_record,
    make_device_info,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_device_mock(
    info=None,
    users=None,
    attendance=None,
    connect_side_effect=None,
):
    """
    Build a MagicMock that impersonates SpeedFaceDevice.
    connect() returns 50.0 (ms) by default.
    get_device_info(), get_users(), get_attendance() return supplied data.
    """
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__  = MagicMock(return_value=False)

    if connect_side_effect:
        mock.connect.side_effect = connect_side_effect
    else:
        mock.connect.return_value = 50.0

    mock.get_device_info.return_value = info or make_device_info()
    mock.get_users.return_value       = users or []

    att = attendance if attendance is not None else []
    mock.get_attendance.return_value  = (att, None)

    mock.disconnect.return_value = None
    return mock


def _patch_device(mock):
    """Context-manager patcher for SpeedFaceDevice in sync_engine."""
    return patch('app.sync_engine.SpeedFaceDevice', return_value=mock)


# ---------------------------------------------------------------------------
# Test: successful sync
# ---------------------------------------------------------------------------

class TestRunSyncSuccess:
    def test_full_sync_inserts_records(self, device_cfg, sync_cfg):
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10),
            make_attendance_record('1002', '2026-08-13 08:05:00', 0, 10),
            make_attendance_record('1001', '2026-08-13 17:00:00', 1, 10),
        ]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            result = run_sync(device_cfg, sync_cfg)

        assert result.status           == 'success'
        assert result.records_read     == 3
        assert result.records_inserted == 3
        assert result.records_skipped  == 0
        assert result.records_failed   == 0
        assert result.duration_s       > 0

    def test_sync_run_recorded_in_db(self, device_cfg, sync_cfg):
        records = [make_attendance_record()]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        conn = db.get_connection(sync_cfg.db_path)
        device_row = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert device_row is not None

        last_run = db.get_last_sync_run(conn, device_row['id'])
        assert last_run is not None
        assert last_run['status']           == 'success'
        assert last_run['records_inserted'] == 1
        conn.close()

    def test_sync_state_updated_after_success(self, device_cfg, sync_cfg):
        records = [make_attendance_record('1001', '2026-08-13 08:00:00')]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        conn = db.get_connection(sync_cfg.db_path)
        device_row = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        state = db.get_sync_state(conn, device_row['id'])
        assert state is not None
        assert state['last_successful_sync_at']     is not None
        assert state['last_device_record_datetime'] == '2026-08-13 08:00:00'
        conn.close()

    def test_device_info_stored(self, device_cfg, sync_cfg):
        info = make_device_info(serial='SN-XYZ-999', firmware='Ver 6.60 Aug 28 2020')
        mock = _make_device_mock(info=info)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        conn = db.get_connection(sync_cfg.db_path)
        row = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert row['serial_number']    == 'SN-XYZ-999'
        assert row['firmware_version'] == 'Ver 6.60 Aug 28 2020'
        conn.close()

    def test_throughput_calculated(self, device_cfg, sync_cfg):
        records = [make_attendance_record(str(i), f'2026-08-13 0{i % 9}:00:00')
                   for i in range(10)]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            result = run_sync(device_cfg, sync_cfg)
        assert result.records_per_second() > 0


# ---------------------------------------------------------------------------
# Test: duplicate protection
# ---------------------------------------------------------------------------

class TestDuplicateProtection:
    def test_second_sync_inserts_zero(self, device_cfg, sync_cfg):
        """
        CRITICAL DUPLICATE TEST:
          Sync #1 → 3 inserted
          Sync #2 (same records) → 0 inserted, 3 skipped
          DB count remains 3
        """
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 08:05:00'),
            make_attendance_record('1001', '2026-08-13 17:00:00', status=1),
        ]
        mock = _make_device_mock(attendance=records)

        with _patch_device(mock):
            r1 = run_sync(device_cfg, sync_cfg)
        assert r1.records_inserted == 3

        with _patch_device(mock):
            r2 = run_sync(device_cfg, sync_cfg)
        assert r2.records_inserted == 0
        assert r2.records_skipped  == 3
        assert r2.status           == 'success'

        conn = db.get_connection(sync_cfg.db_path)
        dev  = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert db.get_attendance_count(conn, dev['id']) == 3
        conn.close()

    def test_multiple_syncs_never_exceed_device_count(self, device_cfg, sync_cfg):
        records = [make_attendance_record(str(i), f'2026-08-0{(i%9)+1} 08:00:00')
                   for i in range(9)]
        mock = _make_device_mock(attendance=records)

        for _ in range(5):
            with _patch_device(mock):
                run_sync(device_cfg, sync_cfg)

        conn = db.get_connection(sync_cfg.db_path)
        dev  = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert db.get_attendance_count(conn, dev['id']) == 9
        conn.close()


# ---------------------------------------------------------------------------
# Test: incremental simulation
# ---------------------------------------------------------------------------

class TestIncrementalSync:
    def test_new_record_added_after_initial_sync(self, device_cfg, sync_cfg):
        """
        INCREMENTAL TEST:
          Initial sync  → 3 records inserted
          New punch on device → device now has 4 records
          Second sync   → 1 new record inserted, 3 skipped
          DB total      → 4
        """
        initial_records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 08:05:00'),
            make_attendance_record('1001', '2026-08-13 17:00:00', status=1),
        ]
        mock1 = _make_device_mock(attendance=initial_records)
        with _patch_device(mock1):
            r1 = run_sync(device_cfg, sync_cfg)
        assert r1.records_inserted == 3

        # One new punch added on the device
        updated_records = initial_records + [
            make_attendance_record('1002', '2026-08-13 17:30:00', status=1),
        ]
        mock2 = _make_device_mock(attendance=updated_records)
        with _patch_device(mock2):
            r2 = run_sync(device_cfg, sync_cfg)

        assert r2.records_inserted == 1
        assert r2.records_skipped  == 3

        conn = db.get_connection(sync_cfg.db_path)
        dev  = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert db.get_attendance_count(conn, dev['id']) == 4
        conn.close()

    def test_zero_records_on_device_is_handled(self, device_cfg, sync_cfg):
        mock = _make_device_mock(attendance=[])
        with _patch_device(mock):
            result = run_sync(device_cfg, sync_cfg)
        assert result.records_read     == 0
        assert result.records_inserted == 0
        assert result.status           == 'success'


# ---------------------------------------------------------------------------
# Test: dry-run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_makes_no_db_changes(self, device_cfg, dry_run_sync_cfg):
        """
        DRY-RUN TEST: no rows written to attendance_records.

        When the device does not yet have a local DB row (first ever run,
        dry_run=True), the engine uses device_id=-1 sentinel and skips
        batch processing to avoid writing anything.  records_read is set
        correctly; inserted/skipped remain 0 because no comparison is
        possible without a device row.  The critical assertion is that
        the attendance_records table stays empty.
        """
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 08:05:00'),
        ]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            result = run_sync(device_cfg, dry_run_sync_cfg)

        assert result.dry_run      == True
        assert result.records_read == 2
        # inserted+skipped may both be 0 when no device row exists yet —
        # the key guarantee is that nothing was written to the DB.
        assert result.records_failed == 0

        # ── THE CRITICAL ASSERTION ────────────────────────────────────────
        # No attendance rows must exist in the database after a dry-run.
        conn = db.get_connection(dry_run_sync_cfg.db_path)
        att_count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records"
        ).fetchone()[0]
        assert att_count == 0, (
            f"Dry-run must not write attendance rows — found {att_count}"
        )
        conn.close()

    def test_dry_run_after_real_sync_shows_all_as_skipped(
        self, device_cfg, sync_cfg, dry_run_sync_cfg
    ):
        """After a real sync, dry-run of same records reports all as skipped."""
        records = [make_attendance_record('1001', '2026-08-13 08:00:00')]
        mock = _make_device_mock(attendance=records)

        # Real sync first
        with _patch_device(mock):
            r1 = run_sync(device_cfg, sync_cfg)
        assert r1.records_inserted == 1

        # Now dry-run with same records
        dry_cfg = SyncConfig(
            dry_run     = True,
            batch_size  = 100,
            max_retries = 1,
            retry_delays= [0],
            db_path     = sync_cfg.db_path,   # same DB
        )
        with _patch_device(mock):
            r2 = run_sync(device_cfg, dry_cfg)

        assert r2.dry_run          == True
        assert r2.records_skipped  == 1
        assert r2.records_inserted == 0

        # DB count unchanged
        conn = db.get_connection(sync_cfg.db_path)
        dev  = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert db.get_attendance_count(conn, dev['id']) == 1
        conn.close()

    def test_dry_run_does_not_update_sync_state(self, device_cfg, dry_run_sync_cfg):
        """Dry-run must not update sync_state checkpoint."""
        records = [make_attendance_record('1001', '2026-08-13 08:00:00')]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            run_sync(device_cfg, dry_run_sync_cfg)

        conn = db.get_connection(dry_run_sync_cfg.db_path)
        # No device row in DB during dry-run (device_id=-1), so no sync_state
        state_count = conn.execute("SELECT COUNT(*) FROM sync_state").fetchone()[0]
        assert state_count == 0
        conn.close()


# ---------------------------------------------------------------------------
# Test: connection failure and retry
# ---------------------------------------------------------------------------

class TestRetry:
    def test_connection_failure_returns_failed_status(self, device_cfg, sync_cfg):
        mock = _make_device_mock(
            connect_side_effect=DeviceConnectionError("Connection refused")
        )
        with _patch_device(mock):
            result = run_sync(device_cfg, sync_cfg)

        assert result.status        == 'failed'
        assert result.error_message is not None
        assert 'Failed to connect'  in result.error_message

    def test_retry_succeeds_on_second_attempt(self, device_cfg, sync_cfg):
        """First connect fails, second succeeds."""
        call_count = {'n': 0}

        def flaky_connect():
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise DeviceConnectionError("Temporary failure")
            return 50.0   # ms

        cfg_with_retry = SyncConfig(
            dry_run     = False,
            batch_size  = 100,
            max_retries = 2,
            retry_delays= [0],
            db_path     = sync_cfg.db_path,
        )
        records = [make_attendance_record('1001', '2026-08-13 08:00:00')]
        mock = _make_device_mock(attendance=records)
        mock.connect.side_effect = flaky_connect

        with _patch_device(mock):
            result = run_sync(device_cfg, cfg_with_retry)

        assert result.status           == 'success'
        assert result.records_inserted == 1
        assert call_count['n']         == 2

    def test_all_retries_exhausted_returns_failed(self, device_cfg, sync_cfg):
        cfg_with_retry = SyncConfig(
            dry_run     = False,
            batch_size  = 100,
            max_retries = 3,
            retry_delays= [0, 0],
            db_path     = sync_cfg.db_path,
        )
        mock = _make_device_mock(
            connect_side_effect=DeviceConnectionError("Always fails")
        )
        with _patch_device(mock):
            result = run_sync(device_cfg, cfg_with_retry)

        assert result.status == 'failed'
        assert mock.connect.call_count == 3


# ---------------------------------------------------------------------------
# Test: partial failure / data integrity
# ---------------------------------------------------------------------------

class TestPartialFailure:
    def test_committed_data_survives_later_batch_error(
        self, device_cfg, sync_cfg
    ):
        """
        If a batch fails partway through, previously committed batches
        must remain intact in the DB.
        """
        # 150 records split across 2 batches of 100 each (batch_size=100)
        first_batch = [
            make_attendance_record(str(i), f'2026-08-{(i%28)+1:02d} 08:00:00')
            for i in range(100)
        ]
        second_batch = [
            make_attendance_record(str(i+100), f'2026-09-{(i%28)+1:02d} 08:00:00')
            for i in range(50)
        ]
        all_records = first_batch + second_batch
        mock = _make_device_mock(attendance=all_records)

        original_insert = db.insert_attendance_batch
        call_count = {'n': 0}

        def patched_insert(conn, device_id, batch, dry_run=False):
            call_count['n'] += 1
            if call_count['n'] == 2:
                raise Exception("Simulated DB failure on batch 2")
            return original_insert(conn, device_id, batch, dry_run=dry_run)

        with _patch_device(mock):
            with patch('app.sync_engine.db.insert_attendance_batch', side_effect=patched_insert):
                result = run_sync(device_cfg, sync_cfg)

        # Status should be partial or failed, not success
        assert result.status in ('partial', 'failed')

        # First 100 records must still be in the DB
        conn = db.get_connection(sync_cfg.db_path)
        dev  = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        stored = db.get_attendance_count(conn, dev['id'])
        assert stored == 100, (
            f"First batch of 100 should survive — found {stored}"
        )
        conn.close()


# ---------------------------------------------------------------------------
# Test: user sync
# ---------------------------------------------------------------------------

class TestRunSyncUsers:
    def test_insert_new_users(self, device_cfg, sync_cfg):
        users = [
            make_user_record(1, '1001', 'Alice'),
            make_user_record(2, '1002', 'Bob'),
        ]
        mock = _make_device_mock(users=users)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock):
            result = run_sync_users(device_cfg, sync_cfg)

        assert result['status']     == 'success'
        assert result['total_read'] == 2
        assert result['inserted']   == 2
        assert result['updated']    == 0
        assert result['unchanged']  == 0

    def test_update_existing_user(self, device_cfg, sync_cfg):
        # Initial sync
        users_v1 = [make_user_record(1, '1001', 'Alice')]
        mock1 = _make_device_mock(users=users_v1)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock1):
            run_sync_users(device_cfg, sync_cfg)

        # Name changed on device
        users_v2 = [make_user_record(1, '1001', 'Alice Renamed')]
        mock2 = _make_device_mock(users=users_v2)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock2):
            result = run_sync_users(device_cfg, sync_cfg)

        assert result['updated']   == 1
        assert result['inserted']  == 0
        assert result['unchanged'] == 0

    def test_unchanged_user_not_counted_as_update(self, device_cfg, sync_cfg):
        users = [make_user_record(1, '1001', 'Alice')]
        mock = _make_device_mock(users=users)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock):
            run_sync_users(device_cfg, sync_cfg)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock):
            result = run_sync_users(device_cfg, sync_cfg)

        assert result['unchanged'] == 1
        assert result['inserted']  == 0
        assert result['updated']   == 0

    def test_new_user_added_on_second_sync(self, device_cfg, sync_cfg):
        users_v1 = [make_user_record(1, '1001', 'Alice')]
        mock1 = _make_device_mock(users=users_v1)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock1):
            run_sync_users(device_cfg, sync_cfg)

        users_v2 = users_v1 + [make_user_record(2, '1002', 'Bob')]
        mock2 = _make_device_mock(users=users_v2)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock2):
            result = run_sync_users(device_cfg, sync_cfg)

        assert result['inserted']  == 1
        assert result['unchanged'] == 1

    def test_user_sync_connection_failure(self, device_cfg, sync_cfg):
        mock = _make_device_mock(
            connect_side_effect=DeviceConnectionError("Refused")
        )
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock):
            result = run_sync_users(device_cfg, sync_cfg)

        assert result['status'] == 'failed'
        assert result['error']  is not None


# ---------------------------------------------------------------------------
# Test: refresh device
# ---------------------------------------------------------------------------

class TestRefreshDevice:
    def test_stores_device_info(self, device_cfg, sync_cfg):
        info = make_device_info(serial='ABC123', firmware='Ver 6.60 Aug 28 2020')
        mock = _make_device_mock(info=info)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock):
            result = run_refresh_device(device_cfg, sync_cfg)

        assert result['status']           == 'success'
        assert result['info']['serial_number'] == 'ABC123'
        assert result['device_id']        > 0

        conn = db.get_connection(sync_cfg.db_path)
        row  = db.get_device_by_ip_port(conn, device_cfg.ip, device_cfg.port)
        assert row['serial_number']    == 'ABC123'
        assert row['firmware_version'] == 'Ver 6.60 Aug 28 2020'
        conn.close()

    def test_refresh_device_connection_failure(self, device_cfg, sync_cfg):
        mock = _make_device_mock(
            connect_side_effect=DeviceConnectionError("Offline")
        )
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock):
            result = run_refresh_device(device_cfg, sync_cfg)

        assert result['status'] == 'failed'
        assert result['error']  is not None


# ---------------------------------------------------------------------------
# Test: sync status
# ---------------------------------------------------------------------------

class TestGetSyncStatus:
    def test_status_before_any_sync(self, device_cfg, sync_cfg):
        # DB initialised but device not yet synced
        db.init_db(sync_cfg.db_path)
        status = get_sync_status(device_cfg, sync_cfg.db_path)
        assert status['device_found']       == False
        assert status['local_record_count'] == 0

    def test_status_after_sync(self, device_cfg, sync_cfg):
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 17:00:00'),
        ]
        mock = _make_device_mock(
            info=make_device_info(serial='SN001'),
            attendance=records,
        )
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        status = get_sync_status(device_cfg, sync_cfg.db_path)
        assert status['device_found']       == True
        assert status['local_record_count'] == 2
        assert status['last_sync_status']   == 'success'
        assert status['last_sync_at']       is not None
        assert status['total_sync_runs']    == 1

    def test_status_tracks_multiple_runs(self, device_cfg, sync_cfg):
        records = [make_attendance_record()]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        status = get_sync_status(device_cfg, sync_cfg.db_path)
        assert status['total_sync_runs'] == 2


# ---------------------------------------------------------------------------
# Test: device safety
# ---------------------------------------------------------------------------

class TestDeviceSafety:
    def test_safety_check_passes_when_counts_unchanged(self, device_cfg, sync_cfg):
        info = make_device_info(users=97, records=99952)
        mock = _make_device_mock(info=info, attendance=[make_attendance_record()])
        with _patch_device(mock):
            result = run_sync(device_cfg, sync_cfg)

        assert result.device_users_before      == 97
        assert result.device_attendance_before == 99952
        # After snapshot equals before (sync never changes device counts)
        assert result.device_users_after      == result.device_users_before
        assert result.device_attendance_after == result.device_attendance_before
        assert result.safety_check_passed()   == True

    def test_safety_check_passes_when_counts_unavailable(self, device_cfg, sync_cfg):
        info = make_device_info()
        info['users']   = 'Not available through this protocol'
        info['records'] = 'Not available through this protocol'
        mock = _make_device_mock(info=info)
        with _patch_device(mock):
            result = run_sync(device_cfg, sync_cfg)

        # When counts are unavailable, safety check returns True (cannot verify)
        assert result.device_users_before is None
        assert result.safety_check_passed() == True


# ---------------------------------------------------------------------------
# Test: data integrity verification
# ---------------------------------------------------------------------------

class TestVerifyIntegrity:
    def test_perfect_match(self, device_cfg, sync_cfg):
        records = [
            make_attendance_record('1001', '2026-08-13 08:00:00'),
            make_attendance_record('1002', '2026-08-13 08:05:00'),
        ]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        result = verify_integrity(device_cfg, 2, sync_cfg.db_path)
        assert result['match']                    == True
        assert result['difference']               == 0
        assert result['device_records_fetched']   == 2
        assert result['local_records_stored']     == 2

    def test_mismatch_reported(self, device_cfg, sync_cfg):
        records = [make_attendance_record('1001', '2026-08-13 08:00:00')]
        mock = _make_device_mock(attendance=records)
        with _patch_device(mock):
            run_sync(device_cfg, sync_cfg)

        # Claim device had 5 records but only 1 was stored
        result = verify_integrity(device_cfg, 5, sync_cfg.db_path)
        assert result['match']      == False
        assert result['difference'] == 4

    def test_device_not_found_returns_error(self, device_cfg, sync_cfg):
        db.init_db(sync_cfg.db_path)
        result = verify_integrity(device_cfg, 10, sync_cfg.db_path)
        assert 'error' in result
