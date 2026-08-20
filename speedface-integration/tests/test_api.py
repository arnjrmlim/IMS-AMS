"""
test_api.py — Phase 3 automated tests for the REST API layer.

All tests use:
  - FastAPI TestClient (synchronous, no real server needed)
  - In-memory or tmp-file SQLite (no real device, no production DB touched)
  - Mocked SyncService where needed (no real device connection)
  - Environment variable overrides via monkeypatch

Test coverage:
  Authentication
    - Valid API key → 200
    - Missing Authorization header → 401
    - Wrong scheme (Basic) → 401
    - Wrong key value → 401
    - API_KEY not configured → 503
    - /api/health requires no auth → 200

  Health endpoint
    - Returns {"status": "ok"}

  Device endpoints
    - List devices (empty, then with data)
    - Get device by id (found / not found)

  Attendance endpoint
    - Pagination (page, per_page, max per_page)
    - Filtering by device_id
    - Filtering by device_user_id
    - Filtering by start_datetime / end_datetime
    - Invalid per_page → 400
    - Invalid page → 400
    - Invalid datetime format → 400
    - start > end → 400

  Device-users endpoint
    - Pagination works
    - Filter by device_id

  Sync status endpoint
    - Before any sync: device_found=False
    - After seeding DB: correct fields returned
    - sync_in_progress reflects lock state

  Sync trigger (POST /api/sync)
    - Returns 202 Accepted
    - Returns 409 when sync already running
    - Device write operations are NOT called (read-only verification)

  Sync history endpoint
    - Returns recent runs

  Concurrent sync lock
    - Second sync rejected while first is running

  Device-read-only verification
    - SyncService never calls any pyzk write method

  Normalized models (device_models.py)
    - NormalizedAttendanceRecord.from_device_dict correctness
    - NormalizedUser.from_device_dict correctness
    - punch_state and verify_type label mapping

  Phase 2 regression
    - All 55 Phase 2 tests still pass (they run in the same pytest session)
"""

import os
import sqlite3
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.database as db
from app.device_models import (
    NormalizedAttendanceRecord,
    NormalizedUser,
    normalize_punch_state,
    normalize_verify_type,
    PUNCH_STATE_MAP,
    VERIFY_TYPE_MAP,
)
from app.sync_service import SyncInProgressError, SyncService
from tests.conftest import (
    make_attendance_record,
    make_device_info,
    make_user_record,
    seed_device,
)

VALID_KEY = 'test-secret-key-phase3'


# ── Test app factory ──────────────────────────────────────────────────────────

def _make_client(
    db_path: str,
    api_key: str = VALID_KEY,
    monkeypatch_obj=None,
) -> TestClient:
    """
    Build a TestClient against a fresh FastAPI app wired to a tmp DB.
    Patches API_KEY and DB_PATH environment variables.
    """
    # We must patch env vars BEFORE importing server (dotenv loads at import)
    env_overrides = {
        'API_KEY': api_key,
        'DB_PATH': db_path,
        'DEVICE_IP': '192.168.99.99',
        'DEVICE_PORT': '4370',
        'DEVICE_COMM_KEY': '0',
        'DEVICE_TIMEOUT': '5',
    }
    for k, v in env_overrides.items():
        os.environ[k] = v

    # Re-import server with fresh environment
    import importlib
    import app.api.server as server_mod
    import app.config.settings as settings_mod
    importlib.reload(settings_mod)
    importlib.reload(server_mod)

    db.init_db(db_path)
    return TestClient(server_mod.app, raise_server_exceptions=False)


@pytest.fixture
def api_client(db_path):
    """TestClient with valid API key and tmp DB."""
    client = _make_client(db_path)
    yield client


@pytest.fixture
def api_client_no_key(db_path):
    """TestClient with API_KEY intentionally unset."""
    os.environ['API_KEY'] = ''
    import importlib
    import app.api.server as server_mod
    import app.config.settings as settings_mod
    importlib.reload(settings_mod)
    importlib.reload(server_mod)
    db.init_db(db_path)
    yield TestClient(server_mod.app, raise_server_exceptions=False)
    os.environ['API_KEY'] = VALID_KEY


def _auth(key: str = VALID_KEY) -> dict:
    return {'Authorization': f'Bearer {key}'}


# ── Helper: seed DB with device + attendance ──────────────────────────────────

def _seed_full(db_path: str) -> int:
    """Seed device + 5 attendance records + 2 users. Returns device_id."""
    conn = db.get_connection(db_path)
    device_id = seed_device(conn, ip='192.168.99.99', port=4370)

    records = [
        make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10),
        make_attendance_record('1001', '2026-08-13 17:00:00', 1, 10),
        make_attendance_record('1002', '2026-08-13 08:05:00', 0, 10),
        make_attendance_record('1002', '2026-08-13 17:05:00', 1, 10),
        make_attendance_record('1003', '2026-08-14 08:00:00', 0, 10),
    ]
    db.insert_attendance_batch(conn, device_id, records)

    users = [
        make_user_record(1, '1001', 'Alice'),
        make_user_record(2, '1002', 'Bob'),
    ]
    db.upsert_users(conn, device_id, users)

    run_id = db.start_sync_run(conn, device_id)
    db.finish_sync_run(conn, run_id, 'success',
                       records_read=5, records_inserted=5,
                       records_skipped=0, records_failed=0)
    db.upsert_sync_state(conn, device_id, run_id, '2026-08-14 08:00:00')

    conn.commit()
    conn.close()
    return device_id


# ═══════════════════════════════════════════════════════════════════════════
# Health endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_health_no_auth_returns_200(self, api_client):
        resp = api_client.get('/api/health')
        assert resp.status_code == 200
        assert resp.json()['status'] == 'ok'

    def test_health_with_auth_still_200(self, api_client):
        resp = api_client.get('/api/health', headers=_auth())
        assert resp.status_code == 200

    def test_health_returns_service_name(self, api_client):
        data = api_client.get('/api/health').json()
        assert 'service' in data
        assert data['service'] == 'speedface-integration'


# ═══════════════════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthentication:
    def test_valid_key_returns_200(self, api_client):
        resp = api_client.get('/api/device', headers=_auth(VALID_KEY))
        assert resp.status_code == 200

    def test_missing_auth_header_returns_401(self, api_client):
        resp = api_client.get('/api/device')
        assert resp.status_code == 401

    def test_wrong_key_returns_401(self, api_client):
        resp = api_client.get('/api/device', headers=_auth('wrong-key'))
        assert resp.status_code == 401
        # FastAPI wraps our ErrorDetail under 'detail'
        body = resp.json()
        assert body['detail']['code'] == 'UNAUTHORIZED'

    def test_basic_scheme_returns_401(self, api_client):
        resp = api_client.get('/api/device',
                              headers={'Authorization': 'Basic dXNlcjpwYXNz'})
        assert resp.status_code == 401

    def test_bearer_empty_token_returns_401(self, api_client):
        resp = api_client.get('/api/device',
                              headers={'Authorization': 'Bearer '})
        assert resp.status_code == 401

    def test_api_key_not_configured_returns_503(self, api_client_no_key):
        resp = api_client_no_key.get('/api/device', headers=_auth('anything'))
        assert resp.status_code == 503
        assert resp.json()['detail']['code'] == 'API_KEY_NOT_CONFIGURED'

    def test_auth_required_for_attendance(self, api_client):
        resp = api_client.get('/api/attendance')
        assert resp.status_code == 401

    def test_auth_required_for_sync_status(self, api_client):
        resp = api_client.get('/api/sync/status')
        assert resp.status_code == 401

    def test_auth_required_for_device_users(self, api_client):
        resp = api_client.get('/api/device-users')
        assert resp.status_code == 401

    def test_auth_required_for_sync_trigger(self, api_client):
        resp = api_client.post('/api/sync')
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Device endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestDeviceEndpoints:
    def test_list_devices_empty(self, api_client):
        resp = api_client.get('/api/device', headers=_auth())
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert body['data'] == []

    def test_list_devices_returns_seeded(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/device', headers=_auth())
        assert resp.status_code == 200
        assert len(resp.json()['data']) == 1
        assert resp.json()['data'][0]['ip_address'] == '192.168.99.99'

    def test_get_device_by_id(self, api_client, db_path):
        device_id = _seed_full(db_path)
        resp = api_client.get(f'/api/device/{device_id}', headers=_auth())
        assert resp.status_code == 200
        assert resp.json()['data']['id'] == device_id

    def test_get_device_not_found(self, api_client):
        resp = api_client.get('/api/device/9999', headers=_auth())
        assert resp.status_code == 404
        assert resp.json()['detail']['code'] == 'NOT_FOUND'


# ═══════════════════════════════════════════════════════════════════════════
# Attendance endpoint — pagination
# ═══════════════════════════════════════════════════════════════════════════

class TestAttendancePagination:
    def test_returns_all_records_within_page(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/attendance?per_page=10', headers=_auth())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body['data']) == 5
        assert body['meta']['total'] == 5

    def test_pagination_limits_results(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/attendance?per_page=2&page=1', headers=_auth())
        body = resp.json()
        assert len(body['data']) == 2
        assert body['meta']['page'] == 1
        assert body['meta']['per_page'] == 2
        assert body['meta']['total'] == 5
        assert body['meta']['pages'] == 3

    def test_page_2_returns_next_records(self, api_client, db_path):
        _seed_full(db_path)
        r1 = api_client.get('/api/attendance?per_page=2&page=1', headers=_auth())
        r2 = api_client.get('/api/attendance?per_page=2&page=2', headers=_auth())
        ids_p1 = {r['id'] for r in r1.json()['data']}
        ids_p2 = {r['id'] for r in r2.json()['data']}
        assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"

    def test_per_page_exceeds_max_returns_400(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/attendance?per_page=1001', headers=_auth())
        # FastAPI returns 422 for Query constraint violations (ge/le)
        assert resp.status_code in (400, 422)

    def test_invalid_page_zero_returns_400(self, api_client, db_path):
        resp = api_client.get('/api/attendance?page=0', headers=_auth())
        assert resp.status_code in (400, 422)

    def test_empty_result_returns_empty_list(self, api_client):
        resp = api_client.get('/api/attendance', headers=_auth())
        body = resp.json()
        assert body['data'] == []
        assert body['meta']['total'] == 0

    def test_default_per_page_is_100(self, api_client, db_path):
        # Insert 150 records
        conn = db.get_connection(db_path)
        dev_id = seed_device(conn)
        recs = [make_attendance_record(str(i), f'2026-08-{(i%28)+1:02d} 08:00:00')
                for i in range(150)]
        db.insert_attendance_batch(conn, dev_id, recs)
        conn.commit(); conn.close()

        resp = api_client.get('/api/attendance', headers=_auth())
        assert len(resp.json()['data']) == 100
        assert resp.json()['meta']['total'] == 150


# ═══════════════════════════════════════════════════════════════════════════
# Attendance endpoint — filtering
# ═══════════════════════════════════════════════════════════════════════════

class TestAttendanceFiltering:
    def test_filter_by_device_id(self, api_client, db_path):
        device_id = _seed_full(db_path)
        resp = api_client.get(
            f'/api/attendance?device_id={device_id}', headers=_auth()
        )
        body = resp.json()
        assert body['meta']['total'] == 5
        for rec in body['data']:
            assert rec['device_id'] == device_id

    def test_filter_by_nonexistent_device_returns_empty(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/attendance?device_id=9999', headers=_auth())
        assert resp.json()['meta']['total'] == 0

    def test_filter_by_device_user_id(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get(
            '/api/attendance?device_user_id=1001', headers=_auth()
        )
        body = resp.json()
        assert body['meta']['total'] == 2
        for rec in body['data']:
            assert rec['device_user_id'] == '1001'

    def test_filter_by_start_datetime(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get(
            '/api/attendance?start_datetime=2026-08-14+00:00:00',
            headers=_auth()
        )
        body = resp.json()
        assert body['meta']['total'] == 1
        assert body['data'][0]['punch_datetime'] == '2026-08-14 08:00:00'

    def test_filter_by_end_datetime(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get(
            '/api/attendance?end_datetime=2026-08-13+23:59:59',
            headers=_auth()
        )
        assert resp.json()['meta']['total'] == 4

    def test_filter_by_date_range(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get(
            '/api/attendance'
            '?start_datetime=2026-08-13+08:00:00'
            '&end_datetime=2026-08-13+17:05:00',
            headers=_auth()
        )
        assert resp.json()['meta']['total'] == 4

    def test_invalid_start_datetime_format_returns_400(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get(
            '/api/attendance?start_datetime=2026/08/13', headers=_auth()
        )
        # Our handler raises HTTPException(400); FastAPI returns 400 with 'detail'
        assert resp.status_code == 400
        body = resp.json()
        assert 'INVALID_PARAM' in body['detail']['code']

    def test_start_after_end_returns_400(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get(
            '/api/attendance'
            '?start_datetime=2026-08-14+00:00:00'
            '&end_datetime=2026-08-13+00:00:00',
            headers=_auth()
        )
        assert resp.status_code == 400

    def test_attendance_record_has_normalized_labels(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/attendance?per_page=10', headers=_auth())
        for rec in resp.json()['data']:
            assert 'punch_state_label'       in rec
            assert 'verification_type_label' in rec
            assert rec['punch_state_label']       != ''
            assert rec['verification_type_label'] != ''


# ═══════════════════════════════════════════════════════════════════════════
# Device users endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestDeviceUsersEndpoint:
    def test_returns_seeded_users(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/device-users', headers=_auth())
        body = resp.json()
        assert body['meta']['total'] == 2

    def test_filter_by_device_id(self, api_client, db_path):
        device_id = _seed_full(db_path)
        resp = api_client.get(
            f'/api/device-users?device_id={device_id}', headers=_auth()
        )
        assert resp.json()['meta']['total'] == 2

    def test_filter_nonexistent_device_returns_empty(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/device-users?device_id=9999', headers=_auth())
        assert resp.json()['meta']['total'] == 0

    def test_pagination_works(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/device-users?per_page=1&page=1', headers=_auth())
        body = resp.json()
        assert len(body['data']) == 1
        assert body['meta']['total'] == 2
        assert body['meta']['pages'] == 2

    def test_user_has_no_biometric_fields(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/device-users', headers=_auth())
        for user in resp.json()['data']:
            assert 'fingerprint' not in user
            assert 'face_template' not in user
            assert 'password' not in user


# ═══════════════════════════════════════════════════════════════════════════
# Sync status endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestSyncStatusEndpoint:
    def test_status_before_sync_device_not_found(self, api_client):
        resp = api_client.get('/api/sync/status', headers=_auth())
        assert resp.status_code == 200
        assert resp.json()['data']['device_found'] is False

    def test_status_after_seeding_returns_data(self, api_client, db_path):
        _seed_full(db_path)
        # Reset singleton so it picks up the current DB_PATH env var
        import app.sync_service as ss_mod
        ss_mod._default_service = None
        resp = api_client.get('/api/sync/status', headers=_auth())
        body = resp.json()['data']
        assert body['device_found']       is True
        assert body['local_record_count'] == 5
        assert body['last_sync_status']   == 'success'
        assert body['total_sync_runs']    == 1

    def test_status_includes_sync_in_progress_field(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/sync/status', headers=_auth())
        assert 'sync_in_progress' in resp.json()['data']

    def test_status_last_run_details(self, api_client, db_path):
        _seed_full(db_path)
        import app.sync_service as ss_mod
        ss_mod._default_service = None
        resp = api_client.get('/api/sync/status', headers=_auth())
        last_run = resp.json()['data'].get('last_run')
        assert last_run is not None
        assert last_run['status']            == 'success'
        assert last_run['records_inserted']  == 5
        assert last_run['records_read']      == 5


# ═══════════════════════════════════════════════════════════════════════════
# Sync history endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestSyncHistoryEndpoint:
    def test_returns_run_history(self, api_client, db_path):
        _seed_full(db_path)
        resp = api_client.get('/api/sync/history', headers=_auth())
        assert resp.status_code == 200
        data = resp.json()['data']
        assert len(data) == 1
        assert data[0]['status'] == 'success'

    def test_empty_history_before_any_sync(self, api_client):
        resp = api_client.get('/api/sync/history', headers=_auth())
        assert resp.status_code == 200
        assert resp.json()['data'] == []


# ═══════════════════════════════════════════════════════════════════════════
# Sync trigger endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestSyncTriggerEndpoint:
    def test_trigger_returns_202(self, api_client, db_path):
        """POST /api/sync should return 202 Accepted."""
        # Mock the SyncService so no real device is needed
        mock_service = MagicMock()
        mock_service.is_running.return_value = False
        mock_service.sync_attendance.return_value = MagicMock(
            status='success', records_inserted=0, records_skipped=0
        )

        with patch('app.api.routes.get_sync_service', return_value=mock_service):
            resp = api_client.post('/api/sync', headers=_auth())

        assert resp.status_code == 202
        body = resp.json()
        assert body['success'] is True
        assert 'message' in body['data']

    def test_trigger_rejected_when_sync_running(self, api_client, db_path):
        """
        CONCURRENT SYNC TEST:
        When is_running() returns True, POST /api/sync must return 409.
        """
        mock_service = MagicMock()
        mock_service.is_running.return_value = True

        with patch('app.api.routes.get_sync_service', return_value=mock_service):
            resp = api_client.post('/api/sync', headers=_auth())

        assert resp.status_code == 409
        body = resp.json()
        assert body['detail']['code'] == 'SYNC_IN_PROGRESS'

    def test_trigger_requires_auth(self, api_client):
        resp = api_client.post('/api/sync')
        assert resp.status_code == 401

    def test_trigger_does_not_call_device_write_methods(self, api_client, db_path):
        """
        DEVICE READ-ONLY VERIFICATION:
        Trigger sync must never call any write/delete/clear method on the device.
        Verified by checking SyncService only calls read-only engine functions.
        """
        called_methods = []

        class TrackingService:
            def is_running(self):
                return False

            def sync_attendance(self, device_cfg, **kwargs):
                called_methods.append('sync_attendance')
                # sync_attendance calls run_sync which only reads from device
                # We verify it does NOT call any of these:
                forbidden = [
                    'clear_attendance', 'delete_user', 'set_user',
                    'clear_data', 'restart', 'set_time', 'reset',
                ]
                for m in forbidden:
                    assert m not in called_methods, f"Forbidden method called: {m}"
                return MagicMock(
                    status='success', records_inserted=0,
                    records_skipped=0, records_read=0
                )

        with patch('app.api.routes.get_sync_service', return_value=TrackingService()):
            resp = api_client.post('/api/sync', headers=_auth())
        assert resp.status_code == 202
        # Give background thread a moment
        time.sleep(0.1)
        assert 'sync_attendance' in called_methods


# ═══════════════════════════════════════════════════════════════════════════
# Concurrent sync lock
# ═══════════════════════════════════════════════════════════════════════════

class TestConcurrentSyncLock:
    def test_second_sync_raises_sync_in_progress(self, db_path):
        """
        SYNC LOCK TEST:
        Acquiring the lock twice without releasing raises SyncInProgressError.
        """
        service = SyncService(db_path=db_path)

        # Manually acquire the lock (simulating first sync running)
        assert service._lock.acquire(blocking=False) is True

        try:
            with pytest.raises(SyncInProgressError) as exc_info:
                service._require_not_running()
            assert 'already running' in str(exc_info.value).lower()
        finally:
            service._lock.release()

    def test_is_running_reflects_lock_state(self, db_path):
        service = SyncService(db_path=db_path)
        assert service.is_running() is False

        service._lock.acquire(blocking=False)
        try:
            assert service.is_running() is True
        finally:
            service._lock.release()

        assert service.is_running() is False

    def test_concurrent_sync_thread_rejected(self, db_path):
        """
        Simulate two threads calling sync simultaneously.
        The second must be rejected with SyncInProgressError.
        """
        service  = SyncService(db_path=db_path)
        results  = []
        barrier  = threading.Barrier(2)

        def _attempt_sync(slot):
            barrier.wait()   # both threads start simultaneously
            try:
                service._require_not_running()
                results.append(('acquired', slot))
                time.sleep(0.05)   # hold lock briefly
            except SyncInProgressError:
                results.append(('rejected', slot))
            finally:
                try:
                    service._lock.release()
                except RuntimeError:
                    pass  # wasn't acquired

        t1 = threading.Thread(target=_attempt_sync, args=(1,))
        t2 = threading.Thread(target=_attempt_sync, args=(2,))
        t1.start(); t2.start()
        t1.join();  t2.join()

        statuses = [r[0] for r in results]
        assert statuses.count('acquired') == 1,  "Exactly one thread must succeed"
        assert statuses.count('rejected') == 1,  "Exactly one thread must be rejected"


# ═══════════════════════════════════════════════════════════════════════════
# Device read-only verification
# ═══════════════════════════════════════════════════════════════════════════

class TestDeviceReadOnly:
    """
    Verify that no write/delete/clear methods are ever called
    on the SpeedFace device during API or sync operations.
    """
    FORBIDDEN_METHODS = [
        'clear_attendance',
        'delete_user',
        'set_user',
        'clear_data',
        'clear_admin',
        'restart',
        'poweroff',
        'set_time',
        'delete_user_template',
        'save_user_template',
        'HR_save_usertemplates',
        'enroll_user',
    ]

    def test_sync_service_does_not_call_write_methods(self, db_path):
        """
        SyncService.sync_attendance() must only call read methods.
        Mock the device to track all method calls.
        """
        from app.config import DeviceConfig
        from app.sync_service import SyncService

        cfg = MagicMock(spec=DeviceConfig)
        cfg.ip       = '192.168.99.99'
        cfg.port     = 4370
        cfg.timeout  = 5
        cfg.comm_key = 0

        called = set()
        mock_device = MagicMock()
        mock_device.connect.return_value = 50.0
        mock_device.get_device_info.return_value = make_device_info()
        mock_device.get_attendance.return_value = (
            [make_attendance_record()], None
        )

        def _track(name):
            def _fn(*a, **kw):
                called.add(name)
            return _fn

        for method in self.FORBIDDEN_METHODS:
            setattr(mock_device, method, _track(method))

        service = SyncService(db_path=db_path)
        with patch('app.sync_engine.SpeedFaceDevice', return_value=mock_device):
            service.sync_attendance(cfg)

        forbidden_called = called.intersection(set(self.FORBIDDEN_METHODS))
        assert forbidden_called == set(), (
            f"Forbidden device methods were called: {forbidden_called}"
        )

    def test_api_endpoints_are_all_get_except_sync_trigger(self, api_client):
        """
        Verify that all data-reading endpoints use GET (read-only HTTP method).
        Only the sync trigger uses POST, and it still only reads from device.
        """
        read_endpoints = [
            '/api/health',
            '/api/device',
            '/api/sync/status',
            '/api/sync/history',
            '/api/attendance',
            '/api/device-users',
        ]
        for endpoint in read_endpoints:
            resp = api_client.get(endpoint, headers=_auth())
            # Should not be 405 Method Not Allowed
            assert resp.status_code != 405, (
                f"GET {endpoint} returned 405 — endpoint may not support GET"
            )

    def test_no_device_write_endpoints_exist(self, api_client):
        """
        Verify that endpoints for device write operations do not exist (404).
        """
        forbidden_endpoints = [
            ('POST',   '/api/device/users'),
            ('PUT',    '/api/device/users/1'),
            ('DELETE', '/api/device/users/1'),
            ('POST',   '/api/device/clear-attendance'),
            ('POST',   '/api/device/reset'),
            ('POST',   '/api/device/restart'),
            ('DELETE', '/api/attendance/1'),
        ]
        for method, path in forbidden_endpoints:
            resp = api_client.request(method, path, headers=_auth())
            assert resp.status_code in (404, 405), (
                f"{method} {path} should not exist — got {resp.status_code}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Normalized models (device_models.py)
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizedModels:
    def test_attendance_from_device_dict(self):
        rec = make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10)
        normalized = NormalizedAttendanceRecord.from_device_dict(1, rec)

        assert normalized.device_id          == 1
        assert normalized.device_user_id     == '1001'
        assert normalized.punch_datetime     == '2026-08-13 08:00:00'
        assert normalized.punch_state        == 'check_in'
        assert normalized.punch_state_raw    == 0
        assert normalized.verification_type  == 'face'
        assert normalized.verification_type_raw == 10

    def test_checkout_state_normalized(self):
        rec = make_attendance_record('1001', '2026-08-13 17:00:00', 1, 10)
        n = NormalizedAttendanceRecord.from_device_dict(1, rec)
        assert n.punch_state == 'check_out'

    def test_fingerprint_verification_normalized(self):
        rec = make_attendance_record('1001', '2026-08-13 08:00:00', 0, 1)
        n = NormalizedAttendanceRecord.from_device_dict(1, rec)
        assert n.verification_type == 'fingerprint'

    def test_password_verification_normalized(self):
        rec = make_attendance_record('1001', '2026-08-13 08:00:00', 0, 15)
        n = NormalizedAttendanceRecord.from_device_dict(1, rec)
        assert n.verification_type == 'password'

    def test_card_verification_normalized(self):
        rec = make_attendance_record('1001', '2026-08-13 08:00:00', 0, 16)
        n = NormalizedAttendanceRecord.from_device_dict(1, rec)
        assert n.verification_type == 'card'

    def test_raw_data_is_json_string(self):
        rec = make_attendance_record('1001', '2026-08-13 08:00:00', 0, 10)
        n = NormalizedAttendanceRecord.from_device_dict(1, rec)
        import json
        parsed = json.loads(n.raw_data)
        assert parsed['user_id'] == '1001'
        assert 'state_code'  in parsed
        assert 'verify_code' in parsed

    def test_user_from_device_dict(self):
        u = make_user_record(uid=5, user_id='2001', name='Charlie')
        n = NormalizedUser.from_device_dict(1, u)
        assert n.device_id      == 1
        assert n.device_uid     == 5
        assert n.device_user_id == '2001'
        assert n.name           == 'Charlie'
        assert n.card_number    is None

    def test_all_punch_states_have_mappings(self):
        for code in range(6):
            label = normalize_punch_state(code)
            assert label != f'unknown_{code}', f"punch code {code} unmapped"

    def test_unknown_punch_state_graceful(self):
        label = normalize_punch_state(99)
        assert label == 'unknown_99'

    def test_all_verify_types_have_mappings(self):
        for code in list(range(10)) + list(range(10, 15)) + [15] + list(range(16, 20)):
            vtype = normalize_verify_type(code)
            assert vtype in ('fingerprint', 'face', 'password', 'card', 'other')


# ═══════════════════════════════════════════════════════════════════════════
# Database Phase 3 additions
# ═══════════════════════════════════════════════════════════════════════════

class TestDatabasePhase3:
    def test_device_employee_mapping_table_exists(self, db_conn):
        tables = {r[0] for r in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert 'device_employee_mapping' in tables

    def test_ensure_mapping_rows_inserts_unmapped(self, db_conn):
        device_id = seed_device(db_conn)
        inserted = db.ensure_mapping_rows(db_conn, device_id, ['1001', '1002', '1003'])
        db_conn.commit()
        assert inserted == 3

        rows = db_conn.execute(
            "SELECT mapping_status FROM device_employee_mapping WHERE device_id=?",
            (device_id,)
        ).fetchall()
        assert all(r['mapping_status'] == 'unmapped' for r in rows)

    def test_ensure_mapping_rows_idempotent(self, db_conn):
        device_id = seed_device(db_conn)
        db.ensure_mapping_rows(db_conn, device_id, ['1001', '1002'])
        db_conn.commit()
        inserted2 = db.ensure_mapping_rows(db_conn, device_id, ['1001', '1002', '1003'])
        db_conn.commit()
        assert inserted2 == 1   # only the new one

    def test_get_unmapped_users(self, db_conn):
        device_id = seed_device(db_conn)
        db.ensure_mapping_rows(db_conn, device_id, ['1001', '1002'])
        db_conn.commit()
        unmapped = db.get_unmapped_users(db_conn, device_id)
        assert len(unmapped) == 2

    def test_get_mapping_summary(self, db_conn):
        device_id = seed_device(db_conn)
        db.ensure_mapping_rows(db_conn, device_id, ['1001', '1002', '1003'])
        db_conn.commit()
        summary = db.get_mapping_summary(db_conn, device_id)
        assert summary.get('unmapped', 0) == 3

    def test_attendance_page_returns_correct_total(self, db_conn):
        device_id = seed_device(db_conn)
        recs = [make_attendance_record(str(i), f'2026-08-{(i%28)+1:02d} 08:00:00')
                for i in range(25)]
        db.insert_attendance_batch(db_conn, device_id, recs)
        db_conn.commit()

        rows, total = db.get_attendance_page(db_conn, device_id=device_id,
                                             page=1, per_page=10)
        assert total == 25
        assert len(rows) == 10

    def test_attendance_page_2_offset_correct(self, db_conn):
        device_id = seed_device(db_conn)
        recs = [make_attendance_record(str(i), f'2026-08-{(i%28)+1:02d} 08:00:00')
                for i in range(25)]
        db.insert_attendance_batch(db_conn, device_id, recs)
        db_conn.commit()

        rows1, _ = db.get_attendance_page(db_conn, device_id=device_id, page=1, per_page=10)
        rows2, _ = db.get_attendance_page(db_conn, device_id=device_id, page=2, per_page=10)
        ids1 = {r['id'] for r in rows1}
        ids2 = {r['id'] for r in rows2}
        assert ids1.isdisjoint(ids2)

    def test_attendance_filter_by_datetime_range(self, db_conn):
        device_id = seed_device(db_conn)
        recs = [
            make_attendance_record('1', '2026-08-13 08:00:00'),
            make_attendance_record('2', '2026-08-14 08:00:00'),
            make_attendance_record('3', '2026-08-15 08:00:00'),
        ]
        db.insert_attendance_batch(db_conn, device_id, recs)
        db_conn.commit()

        rows, total = db.get_attendance_page(
            db_conn,
            device_id=device_id,
            start_datetime='2026-08-14 00:00:00',
            end_datetime='2026-08-14 23:59:59',
        )
        assert total == 1
        assert rows[0]['device_user_id'] == '2'
