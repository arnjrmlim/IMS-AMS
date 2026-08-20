"""
main.py — Command handlers for all CLI operations.

Each function corresponds to one CLI command exposed via run.py:
  test_connection()   → python run.py test-connection
  device_info()       → python run.py device-info
  users()             → python run.py users
  attendance()        → python run.py attendance
  diagnostics()       → python run.py diagnostics

PHASE 1 RULE: All operations are strictly READ-ONLY.
No data is written, modified, or deleted on the device.
"""

import logging
import time
from datetime import datetime

from app.config import DeviceConfig
from app.device import (
    SpeedFaceDevice,
    DeviceConnectionError,
    DeviceReadError,
    check_ip_reachable,
    check_tcp_port,
)

logger = logging.getLogger(__name__)

# ── formatting helpers ──────────────────────────────────────────────────────

SEP  = '=' * 48
SEP2 = '-' * 48
SEP3 = '-' * 64


def _header(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def _field(label: str, value, width: int = 20) -> None:
    print(f"  {label:<{width}}: {value}")


def _pass(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


# ── Part 3 — Connection Test ────────────────────────────────────────────────

def test_connection(debug: bool = False) -> int:
    """
    Attempt to connect to the device, report result, then disconnect cleanly.
    Returns 0 on success, 1 on failure.
    """
    _header("SpeedFace-V5L  —  Connection Test")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("Configuration error: %s", exc)
        return 1

    _field("Device IP",   cfg.ip)
    _field("Device Port", cfg.port)
    _field("Timeout",     f"{cfg.timeout}s")
    _field("Comm Key",    "Set" if cfg.comm_key != 0 else "Not set (0)")
    print()

    device = SpeedFaceDevice(cfg)
    t_start = time.perf_counter()

    try:
        elapsed_ms = device.connect()
        total_ms   = (time.perf_counter() - t_start) * 1000

        _field("Connection",     "SUCCESS")
        _field("Response Time",  f"{elapsed_ms:.0f} ms")
        print()
        print("  Device is reachable and accepted the connection.\n")
        logger.info("test-connection SUCCESS — %.0f ms", elapsed_ms)
        return 0

    except DeviceConnectionError as exc:
        total_ms = (time.perf_counter() - t_start) * 1000
        _field("Connection",    "FAILED")
        _field("Error",         str(exc))
        print()
        print("  Possible causes:")
        print("    - Incorrect IP address or subnet")
        print("    - Incorrect port (default is 4370)")
        print("    - Device is powered off or unreachable")
        print("    - Firewall or switch blocking port 4370")
        print("    - Communication key mismatch")
        print("    - TCP communication not enabled on device")
        print("    - Unsupported firmware / protocol version")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("test-connection FAILED: %s", exc)
        return 1

    except Exception as exc:
        _field("Connection", "FAILED")
        _field("Error",      f"Unexpected: {exc}")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("test-connection unexpected error: %s", exc, exc_info=debug)
        return 1

    finally:
        device.disconnect()


# ── Part 4 — Device Information ─────────────────────────────────────────────

def device_info(debug: bool = False) -> int:
    """
    Connect and retrieve device metadata.
    Returns 0 on success, 1 on failure.
    """
    _header("SpeedFace-V5L  —  Device Information")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("Configuration error: %s", exc)
        return 1

    device = SpeedFaceDevice(cfg)
    try:
        device.connect()
    except DeviceConnectionError as exc:
        print(f"\n  Connection failed: {exc}\n")
        logger.error("device-info: connection failed: %s", exc)
        return 1

    try:
        info = device.get_device_info()
    except Exception as exc:
        print(f"\n  Failed to read device information: {exc}\n")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("device-info read error: %s", exc, exc_info=debug)
        return 1
    finally:
        device.disconnect()

    print()
    _field("Model / Name",      info.get('device_name',      'N/A'), 22)
    _field("Serial Number",     info.get('serial_number',    'N/A'), 22)
    _field("Firmware Version",  info.get('firmware_version', 'N/A'), 22)
    _field("Platform",          info.get('platform',         'N/A'), 22)
    _field("Face Version",      info.get('face_version',     'N/A'), 22)
    _field("Fingerprint Ver.",  info.get('fp_version',       'N/A'), 22)
    _field("MAC Address",       info.get('mac',              'N/A'), 22)

    dev_time = info.get('device_time', 'N/A')
    if isinstance(dev_time, datetime):
        dev_time = dev_time.strftime('%Y-%m-%d %H:%M:%S')
    _field("Device Time",       dev_time, 22)

    print()
    print(f"  {'--- Capacity / Usage ---'}")

    users       = info.get('users',       'N/A')
    records     = info.get('records',     'N/A')
    fingers     = info.get('fingers',     'N/A')
    users_cap   = info.get('users_cap',   'N/A')
    fingers_cap = info.get('fingers_cap', 'N/A')

    _field("User Count",        users,       22)
    _field("Users Capacity",    users_cap,   22)
    _field("Finger Count",      fingers,     22)
    _field("Fingers Capacity",  fingers_cap, 22)
    _field("Attendance Count",  records,     22)

    print()
    logger.info("device-info retrieved successfully")
    return 0


# ── Part 5 — Users ──────────────────────────────────────────────────────────

def users(debug: bool = False) -> int:
    """
    Connect and retrieve all registered users.
    Returns 0 on success, 1 on failure.
    """
    _header("SpeedFace-V5L  —  Device Users")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("Configuration error: %s", exc)
        return 1

    device = SpeedFaceDevice(cfg)
    try:
        device.connect()
    except DeviceConnectionError as exc:
        print(f"\n  Connection failed: {exc}\n")
        logger.error("users: connection failed: %s", exc)
        return 1

    try:
        user_list = device.get_users()
    except DeviceReadError as exc:
        print(f"\n  Failed to read users: {exc}\n")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("users read error: %s", exc, exc_info=debug)
        return 1
    except Exception as exc:
        print(f"\n  Unexpected error: {exc}\n")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("users unexpected error: %s", exc, exc_info=debug)
        return 1
    finally:
        device.disconnect()

    if not user_list:
        print("\n  No users found on device.\n")
        logger.info("users: device returned 0 users")
        return 0

    print()
    # Table header
    print(f"  {'UID':<6}  {'User ID':<12}  {'Name':<24}  {'Privilege':<16}  {'Card'}")
    print(f"  {SEP3}")

    for u in user_list:
        card = str(u['card']) if u['card'] not in (0, None, 'N/A', '') else '-'
        print(
            f"  {str(u['uid']):<6}  "
            f"{str(u['user_id']):<12}  "
            f"{str(u['name']):<24}  "
            f"{u['privilege_label']:<16}  "
            f"{card}"
        )

    print()
    print(f"  Total: {len(user_list)} user(s)\n")
    logger.info("users: retrieved %d users", len(user_list))
    return 0


# ── Part 6 — Attendance ──────────────────────────────────────────────────────

def attendance(debug: bool = False) -> int:
    """
    Connect and retrieve all attendance/transaction records.
    Returns 0 on success, 1 on failure.
    Note: may return 0 records on newer SpeedFace-V5L firmware (known issue).
    """
    _header("SpeedFace-V5L  —  Attendance Records")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("Configuration error: %s", exc)
        return 1

    device = SpeedFaceDevice(cfg)
    try:
        device.connect()
    except DeviceConnectionError as exc:
        print(f"\n  Connection failed: {exc}\n")
        logger.error("attendance: connection failed: %s", exc)
        return 1

    try:
        records, warning = device.get_attendance()
    except DeviceReadError as exc:
        print(f"\n  Failed to read attendance: {exc}\n")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("attendance read error: %s", exc, exc_info=debug)
        return 1
    except Exception as exc:
        print(f"\n  Unexpected error: {exc}\n")
        if debug:
            import traceback
            traceback.print_exc()
        logger.error("attendance unexpected error: %s", exc, exc_info=debug)
        return 1
    finally:
        device.disconnect()

    if warning:
        print()
        print("  [WARNING]")
        # Word-wrap the warning at ~70 chars
        words = warning.split()
        line  = "  "
        for word in words:
            if len(line) + len(word) + 1 > 72:
                print(line)
                line = f"  {word}"
            else:
                line = f"{line} {word}" if line.strip() else f"  {word}"
        if line.strip():
            print(line)
        print()

    if not records:
        print("  No attendance records retrieved.\n")
        logger.info("attendance: 0 records retrieved")
        return 0

    print()
    print(
        f"  {'User ID':<10}  {'Date / Time':<22}  "
        f"{'State':<14}  {'Verification'}"
    )
    print(f"  {SEP3}")

    for r in records:
        ts = r['timestamp']
        if isinstance(ts, datetime):
            ts = ts.strftime('%Y-%m-%d %H:%M:%S')
        print(
            f"  {str(r['user_id']):<10}  "
            f"{str(ts):<22}  "
            f"{r['status_label']:<14}  "
            f"{r['verify_label']}"
        )

    print()
    print(f"  Total: {len(records)} record(s)\n")
    logger.info("attendance: retrieved %d records", len(records))
    return 0


# ── Part 7 — Diagnostics ─────────────────────────────────────────────────────

def diagnostics(debug: bool = False) -> int:
    """
    Run a full 6-step diagnostic and report pass/fail per step.
    Returns 0 if all steps pass, 1 if any step fails.
    """
    _header("SpeedFace-V5L  —  Diagnostics")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("Diagnostics: configuration error: %s", exc)
        return 1

    _field("Device IP",   cfg.ip,      14)
    _field("Device Port", cfg.port,    14)
    _field("Comm Key",    "Set" if cfg.comm_key != 0 else "Not set (0)", 14)
    print()
    print(f"  {'Step':<4}  {'Check':<32}  Result")
    print(f"  {SEP3}")

    results = {}

    # Step 1 — IP reachability
    ok, msg = check_ip_reachable(cfg.ip, timeout=3)
    results['ip'] = ok
    _pass("IP address is valid") if ok else _fail(f"IP check: {msg}")

    # Step 2 — TCP port
    ok, msg = check_tcp_port(cfg.ip, cfg.port, timeout=cfg.timeout)
    results['tcp'] = ok
    _pass(f"TCP port {cfg.port} is reachable") if ok else _fail(f"TCP port: {msg}")

    if not results['tcp']:
        # No point attempting ZK protocol if TCP is closed
        _fail("Device connection  (skipped — TCP port unreachable)")
        _fail("Device information (skipped)")
        _fail("User retrieval     (skipped)")
        _fail("Attendance retrieval (skipped)")
        _overall_result(results)
        return 1

    # Step 3 — ZK protocol connection
    device = SpeedFaceDevice(cfg)
    try:
        elapsed_ms = device.connect()
        results['connect'] = True
        _pass(f"ZK protocol connection ({elapsed_ms:.0f} ms)")
    except DeviceConnectionError as exc:
        results['connect'] = False
        _fail(f"ZK protocol connection: {exc}")
        _fail("Device information (skipped — connection failed)")
        _fail("User retrieval     (skipped — connection failed)")
        _fail("Attendance retrieval (skipped — connection failed)")
        _overall_result(results)
        return 1

    # Step 4 — Device information
    try:
        info = device.get_device_info()
        results['device_info'] = True
        fw  = info.get('firmware_version', 'N/A')
        plat = info.get('platform',        'N/A')
        _pass(f"Device information  (fw={fw}, platform={plat})")
    except Exception as exc:
        results['device_info'] = False
        _fail(f"Device information: {exc}")
        if debug:
            import traceback
            traceback.print_exc()

    # Step 5 — User retrieval
    try:
        user_list = device.get_users()
        results['users'] = True
        _pass(f"User retrieval ({len(user_list)} user(s))")
    except Exception as exc:
        results['users'] = False
        _fail(f"User retrieval: {exc}")
        if debug:
            import traceback
            traceback.print_exc()

    # Step 6 — Attendance retrieval
    try:
        att_records, att_warning = device.get_attendance()
        if att_warning and len(att_records) == 0:
            results['attendance'] = False
            _fail(
                f"Attendance retrieval: 0 records — possible firmware "
                f"compatibility issue (see --debug or run: python run.py attendance)"
            )
        else:
            results['attendance'] = True
            _pass(f"Attendance retrieval ({len(att_records)} record(s))")
    except Exception as exc:
        results['attendance'] = False
        _fail(f"Attendance retrieval: {exc}")
        if debug:
            import traceback
            traceback.print_exc()

    device.disconnect()

    print()
    _overall_result(results)

    all_passed = all(results.values())
    return 0 if all_passed else 1


def _overall_result(results: dict) -> None:
    all_passed = all(results.values())
    if all_passed:
        print(f"  Overall Result : COMPATIBLE\n")
        logger.info("Diagnostics: COMPATIBLE — all steps passed")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  Overall Result : FAILED")
        print(f"  Failed steps   : {', '.join(failed)}\n")
        logger.warning("Diagnostics: FAILED — steps: %s", ', '.join(failed))


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Synchronisation commands
# ═══════════════════════════════════════════════════════════════════════════

from app.sync_engine import (
    SyncConfig,
    run_sync,
    run_sync_users,
    run_refresh_device,
    get_sync_status,
)
import app.database as _db


def _format_duration(seconds: float) -> str:
    """Convert float seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


# ── sync ────────────────────────────────────────────────────────────────────

def sync(dry_run: bool = False, debug: bool = False) -> int:
    """
    Fetch attendance records from the device and store them locally.

    python run.py sync              # live sync
    python run.py sync --dry-run    # preview only — no DB writes, no device changes

    READ-ONLY on device: only get_attendance() / get_device_info() are called.
    No data is written, modified, or deleted on the SpeedFace-V5L.
    """
    if dry_run:
        _header("SpeedFace-V5L  —  Sync (DRY RUN)")
    else:
        _header("SpeedFace-V5L  —  Synchronisation")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("sync: configuration error: %s", exc)
        return 1

    _field("Device IP",    cfg.ip,   16)
    _field("Device Port",  cfg.port, 16)
    _field("Mode",         "DRY RUN — no changes will be made" if dry_run else "LIVE", 16)
    print()

    sync_cfg = SyncConfig(dry_run=dry_run)
    print("  Connecting to device ...")

    result = run_sync(cfg, sync_cfg)

    print()
    if dry_run:
        print("  ── Dry-Run Results ──────────────────────────────")
        _field("Records read",       f"{result.records_read:,}",     22)
        _field("Would insert",       f"{result.records_inserted:,}", 22)
        _field("Would skip",         f"{result.records_skipped:,}",  22)
        if result.records_failed:
            _field("Would fail",     f"{result.records_failed:,}",   22)
        print()
        print("  No local database changes were made.")
        print("  No device data was modified.")
    else:
        _field("Records read",        f"{result.records_read:,}",     22)
        _field("New records",         f"{result.records_inserted:,}", 22)
        _field("Duplicates skipped",  f"{result.records_skipped:,}",  22)
        if result.records_failed:
            _field("Failed",          f"{result.records_failed:,}",   22)
        print()
        status_str = result.status.upper()
        _field("Synchronisation",     status_str, 22)
        _field("Duration",            _format_duration(result.duration_s), 22)
        if result.records_read > 0:
            _field("Throughput",
                   f"{result.records_per_second():.0f} records/s", 22)
        print()
        print("  Device data status : UNCHANGED")
        print("  (Records were READ ONLY. No device records were modified or deleted.)")

    if result.error_message:
        print()
        print(f"  Error: {result.error_message}")
        if debug:
            import traceback
            traceback.print_exc()

    # Device safety note
    if not dry_run and result.device_attendance_before is not None:
        print()
        print("  ── Device Safety Snapshot ───────────────────────")
        _field("Users (before/after)",
               f"{result.device_users_before} / {result.device_users_after}", 26)
        _field("Attendance (before/after)",
               f"{result.device_attendance_before:,} / {result.device_attendance_after:,}", 26)
        if result.safety_check_passed():
            print("  [OK] Device counts are unchanged.")
        else:
            print("  [WARNING] Device counts changed — investigate immediately.")

    print()
    return 0 if result.status in ('success', 'partial') else 1


# ── sync-status ──────────────────────────────────────────────────────────────

def sync_status(debug: bool = False) -> int:
    """
    Display synchronisation status from local database.
    Does NOT connect to the device.
    """
    _header("SpeedFace-V5L  —  Synchronisation Status")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("sync-status: configuration error: %s", exc)
        return 1

    status = get_sync_status(cfg)

    if status.get('error'):
        print(f"\n  Error: {status['error']}\n")
        return 1

    if not status['device_found']:
        print()
        print("  No local record found for this device.")
        print(f"  IP: {cfg.ip}:{cfg.port}")
        print()
        print("  Run 'python run.py sync' to perform the initial synchronisation.")
        print()
        return 0

    print()
    _field("Device",             status.get('device_name') or cfg.ip,   22)
    _field("IP Address",         f"{cfg.ip}:{cfg.port}",                 22)
    _field("Serial Number",      status.get('serial_number') or 'N/A',  22)
    _field("Firmware",           status.get('firmware') or 'N/A',       22)
    _field("Platform",           status.get('platform') or 'N/A',       22)
    print()
    _field("Local Records",      f"{status['local_record_count']:,}",    22)
    _field("Last Record",        status.get('last_record_datetime') or 'None', 22)
    print()
    _field("Last Sync",          status.get('last_sync_at') or 'Never', 22)
    _field("Last Sync Status",   (status.get('last_sync_status') or 'N/A').upper(), 22)
    _field("Total Sync Runs",    status.get('total_sync_runs', 0),       22)

    last_run_inserted = status.get('last_run_inserted')
    last_run_skipped  = status.get('last_run_skipped')
    last_run_read     = status.get('last_run_read')
    if last_run_read is not None:
        print()
        print("  ── Last Sync Run ────────────────────────────────")
        _field("Records Read",    f"{last_run_read:,}",     22)
        _field("Inserted",        f"{last_run_inserted:,}", 22)
        _field("Skipped (dupes)", f"{last_run_skipped:,}",  22)

    print()
    print("  Device Operation   : READ ONLY")
    print("  The sync service never modifies or deletes device records.")
    print()
    logger.info("sync-status displayed successfully")
    return 0


# ── sync-users ───────────────────────────────────────────────────────────────

def sync_users(debug: bool = False) -> int:
    """
    Fetch users from device and update the local device_users table.
    READ-ONLY on device — no users are added/modified/deleted on the device.
    """
    _header("SpeedFace-V5L  —  User Synchronisation")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("sync-users: configuration error: %s", exc)
        return 1

    _field("Device IP",   cfg.ip,   16)
    _field("Device Port", cfg.port, 16)
    print()
    print("  Connecting to device ...")

    sync_cfg = SyncConfig()
    result   = run_sync_users(cfg, sync_cfg)

    print()
    if result['status'] == 'failed':
        print(f"  Sync users FAILED: {result.get('error', 'Unknown error')}")
        if debug:
            import traceback
            traceback.print_exc()
        return 1

    _field("Device users read",  f"{result['total_read']:,}", 22)
    _field("New users",          f"{result['inserted']:,}",   22)
    _field("Updated users",      f"{result['updated']:,}",    22)
    _field("Unchanged",          f"{result['unchanged']:,}",  22)
    print()
    print("  Direction  : SpeedFace → Local database (READ ONLY)")
    print("  No users were added, modified, or deleted on the device.")
    print()
    logger.info(
        "sync-users complete — read=%d inserted=%d updated=%d unchanged=%d",
        result['total_read'], result['inserted'],
        result['updated'], result['unchanged']
    )
    return 0


# ── refresh-device ───────────────────────────────────────────────────────────

def refresh_device(debug: bool = False) -> int:
    """
    Connect to the device, read metadata, and update the local devices table.
    READ-ONLY on device — no settings are changed.
    """
    _header("SpeedFace-V5L  —  Refresh Device Information")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        logger.error("refresh-device: configuration error: %s", exc)
        return 1

    _field("Device IP",   cfg.ip,   16)
    _field("Device Port", cfg.port, 16)
    print()
    print("  Connecting to device ...")

    sync_cfg = SyncConfig()
    result   = run_refresh_device(cfg, sync_cfg)

    if result['status'] == 'failed':
        print(f"\n  Refresh FAILED: {result.get('error', 'Unknown error')}\n")
        if debug:
            import traceback
            traceback.print_exc()
        return 1

    info = result.get('info', {})
    NOT_AVAIL = "Not available through this protocol"

    print()
    print("  ── Device Information (stored locally) ─────────────")
    _field("Model / Name",     info.get('device_name',      NOT_AVAIL), 22)
    _field("Serial Number",    info.get('serial_number',    NOT_AVAIL), 22)
    _field("Firmware Version", info.get('firmware_version', NOT_AVAIL), 22)
    _field("Platform",         info.get('platform',         NOT_AVAIL), 22)
    _field("Face Version",     info.get('face_version',     NOT_AVAIL), 22)
    _field("MAC Address",      info.get('mac',              NOT_AVAIL), 22)

    dev_time = info.get('device_time', NOT_AVAIL)
    if isinstance(dev_time, datetime):
        dev_time = dev_time.strftime('%Y-%m-%d %H:%M:%S')
    _field("Device Time",      dev_time, 22)

    users_val   = info.get('users',   NOT_AVAIL)
    records_val = info.get('records', NOT_AVAIL)
    if isinstance(users_val, int):
        users_val   = f"{users_val:,}"
    if isinstance(records_val, int):
        records_val = f"{records_val:,}"

    _field("User Count",       users_val,   22)
    _field("Attendance Count", records_val, 22)
    print()
    print(f"  Device record stored locally (id={result.get('device_id', '?')}).")
    print()
    logger.info("refresh-device complete — device_id=%s", result.get('device_id'))
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — API server and worker commands
# ═══════════════════════════════════════════════════════════════════════════

def serve(debug: bool = False) -> int:
    """
    Start the Phase 3 REST API server.

    python run.py serve
    python run.py serve --debug

    The server binds to API_HOST:API_PORT (from .env).
    Requires API_KEY to be set in .env.
    """
    from app.config.settings import (
        get_api_host, get_api_port, get_api_reload,
        get_api_key, get_settings_summary,
    )

    _header("SpeedFace-V5L  —  API Server (Phase 3)")

    # Validate API_KEY before starting
    try:
        get_api_key()   # raises if not set
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        print("  Generate a key:  python -c \"import secrets; print(secrets.token_hex(32))\"")
        print("  Then add to .env: API_KEY=<generated_key>\n")
        return 1

    try:
        settings = get_settings_summary()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        return 1

    host    = settings['api_host']
    port    = settings['api_port']
    reload  = settings['api_reload'] or debug

    _field("API Host",        host,   18)
    _field("API Port",        port,   18)
    _field("API Key",         "Set",  18)
    _field("Reload",          reload, 18)
    _field("Sync Interval",   f"{settings['sync_interval_seconds']}s", 18)
    _field("Database",        settings['db_path'], 18)
    print()
    print(f"  Docs : http://{host}:{port}/docs")
    print(f"  API  : http://{host}:{port}/api/health")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    import uvicorn
    uvicorn.run(
        'app.api.server:app',
        host    = host,
        port    = port,
        reload  = reload,
        log_level = 'debug' if debug else 'info',
    )
    return 0


def worker(debug: bool = False) -> int:
    """
    Start the background synchronisation worker.

    python run.py worker

    Connects to the SpeedFace device on the configured interval and
    performs a read-only attendance sync. Never modifies the device.
    """
    from app.config.settings import get_sync_interval, get_db_path

    _header("SpeedFace-V5L  —  Sync Worker (Phase 3)")

    try:
        cfg = DeviceConfig()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        return 1

    try:
        interval = get_sync_interval()
    except ValueError as exc:
        print(f"\n  Configuration error: {exc}\n")
        return 1

    db_path = get_db_path()

    _field("Device IP",        cfg.ip,      18)
    _field("Device Port",      cfg.port,    18)
    _field("Sync Interval",    f"{interval}s", 18)
    _field("Database",         db_path,     18)
    _field("Device Policy",    "READ ONLY", 18)
    print()
    print("  Worker is running. Press Ctrl+C to stop.")
    print()

    from app.sync_service import SyncService, SyncWorker
    service = SyncService(db_path=db_path)
    worker_ = SyncWorker(service, cfg, interval_seconds=interval)

    try:
        worker_.start()   # blocks until Ctrl+C
    except KeyboardInterrupt:
        print("\n  Worker stopped.\n")
    return 0
