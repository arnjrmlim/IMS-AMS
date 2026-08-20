#!/usr/bin/env python3
"""
run.py — CLI entry point for the SpeedFace-V5L integration.

Phase 1 commands (device read-only, no local DB):
    python run.py test-connection       TCP + ZK protocol handshake
    python run.py device-info           Read device metadata
    python run.py users                 List registered users
    python run.py attendance            List attendance records
    python run.py diagnostics           Full 6-step diagnostic

Phase 2 commands (synchronisation service):
    python run.py sync                  Fetch attendance → local SQLite
    python run.py sync --dry-run        Preview sync — no changes made
    python run.py sync-status           Show local sync state
    python run.py sync-users            Sync users to local DB
    python run.py refresh-device        Refresh device info in local DB

Phase 3 commands (API + worker):
    python run.py serve                 Start the REST API server
    python run.py worker                Start the background sync worker

Optional flags (any command):
    --debug         Full tracebacks + DEBUG log output
    --dry-run       (sync only) Preview without writing

DEVICE POLICY: The SpeedFace-V5L is READ-ONLY.
No data is written, modified, or deleted on the device.
"""

import sys
import os

# Ensure the project root is on the path regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.logger_setup import setup_logging

# ── command registry ─────────────────────────────────────────────────────────
COMMANDS = {
    # Phase 1
    'test-connection': 'test_connection',
    'device-info':     'device_info',
    'users':           'users',
    'attendance':      'attendance',
    'diagnostics':     'diagnostics',
    # Phase 2
    'sync':            'sync',
    'sync-status':     'sync_status',
    'sync-users':      'sync_users',
    'refresh-device':  'refresh_device',
    # Phase 3
    'serve':           'serve',
    'worker':          'worker',
}

_DRY_RUN_COMMANDS = {'sync'}

HELP_TEXT = """
SpeedFace-V5L Integration — Phase 1 + Phase 2 + Phase 3
========================================================

Usage:
    python run.py <command> [--debug] [--dry-run]

━━ Phase 1 — Device Read Commands ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    test-connection     Connect to the device and verify the ZK handshake
    device-info         Read device name, firmware, serial, time, counts
    users               List all registered users on the device
    attendance          List all attendance/transaction records
    diagnostics         Run full 6-step compatibility diagnostic

━━ Phase 2 — Synchronisation Commands ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    sync                Fetch attendance records → store in local SQLite DB
    sync --dry-run      Preview sync counts — no DB writes, no device changes
    sync-status         Display current sync state from local database
    sync-users          Sync device users to local database
    refresh-device      Re-read device metadata and update local database

━━ Phase 3 — API + Worker Commands ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    serve               Start the REST API server (requires API_KEY in .env)
    worker              Start the background auto-sync worker

━━ Flags ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    --debug             Enable DEBUG logging and show full tracebacks
    --dry-run           (sync only) Preview without writing to the database

━━ Device Policy ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    The SpeedFace-V5L is READ-ONLY.
    No data is written, modified, or deleted on the device.

━━ Examples ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    python run.py test-connection
    python run.py sync --dry-run
    python run.py sync
    python run.py sync-status
    python run.py serve
    python run.py worker

━━ Configuration ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Copy .env.example to .env:
        DEVICE_IP=192.168.10.3
        DEVICE_PORT=4370
        DEVICE_COMM_KEY=0
        DEVICE_TIMEOUT=10
        API_KEY=<generate with: python -c "import secrets;print(secrets.token_hex(32))">
        API_HOST=127.0.0.1
        API_PORT=8000
        SYNC_INTERVAL_SECONDS=300
"""


def main() -> int:
    args = sys.argv[1:]

    # Parse flags
    debug   = '--debug'   in args
    dry_run = '--dry-run' in args
    # Strip all flags so args[0] is the command
    args = [a for a in args if not a.startswith('--')]

    if not args or args[0] in ('-h', '--help', 'help'):
        print(HELP_TEXT)
        return 0

    command = args[0].lower()

    if command not in COMMANDS:
        print(f"\n  Unknown command: '{command}'")
        print(f"  Run 'python run.py --help' to see available commands.\n")
        return 1

    if dry_run and command not in _DRY_RUN_COMMANDS:
        print(f"\n  --dry-run is only supported for: {', '.join(_DRY_RUN_COMMANDS)}\n")
        return 1

    # Configure logging before any module-level log calls
    setup_logging(debug=debug)

    # Import handler and dispatch
    from app import main as app_main
    handler_name = COMMANDS[command]
    handler = getattr(app_main, handler_name, None)

    if handler is None:
        print(f"  Internal error: handler '{handler_name}' not found in app.main")
        return 1

    # Pass dry_run only to commands that accept it
    if command in _DRY_RUN_COMMANDS:
        return handler(dry_run=dry_run, debug=debug)

    return handler(debug=debug)


if __name__ == '__main__':
    sys.exit(main())
