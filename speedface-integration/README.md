# SpeedFace-V5L Integration — Phase 1 + Phase 2 + Phase 3

A standalone Python service that communicates directly with a **ZKTeco SpeedFace-V5L**
biometric device over LAN, reads attendance and user data, stores a local copy in SQLite,
and exposes the synchronized data through a secure REST API — using only **free,
open-source** libraries.

> **Device Policy — Non-Negotiable:**
> The SpeedFace-V5L is used exclusively as a **read-only** source of attendance and device
> data. The synchronisation and API layer does not modify, delete, clear, overwrite, reset,
> or clean up any data on the device.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Verified Device](#2-verified-device)
3. [Required Python Version](#3-required-python-version)
4. [Free / Open-Source Library](#4-free--open-source-library)
5. [Project Structure](#5-project-structure)
6. [Installation](#6-installation)
7. [Configuration](#7-configuration)
8. [Phase 1 — Device Commands](#8-phase-1--device-commands)
9. [Phase 2 — Synchronisation Commands](#9-phase-2--synchronisation-commands)
10. [Phase 3 — API Server and Worker Commands](#10-phase-3--api-server-and-worker-commands)
11. [Phase 3 Architecture](#11-phase-3-architecture)
12. [Device Communication Layer](#12-device-communication-layer)
13. [Synchronisation Layer](#13-synchronisation-layer)
14. [SQLite Data Layer](#14-sqlite-data-layer)
15. [API Architecture](#15-api-architecture)
16. [API Authentication](#16-api-authentication)
17. [API Endpoints](#17-api-endpoints)
18. [Request / Response Examples](#18-request--response-examples)
19. [Pagination](#19-pagination)
20. [Filtering](#20-filtering)
21. [Sync Process](#21-sync-process)
22. [Duplicate Detection Strategy](#22-duplicate-detection-strategy)
23. [Incremental Synchronisation Strategy](#23-incremental-synchronisation-strategy)
24. [Retry Behaviour](#24-retry-behaviour)
25. [Concurrent Sync Lock](#25-concurrent-sync-lock)
26. [Error Handling](#26-error-handling)
27. [Multi-Device Architecture](#27-multi-device-architecture)
28. [Employee / Device User Mapping](#28-employee--device-user-mapping)
29. [Device Safety Verification](#29-device-safety-verification)
30. [Running the Automated Tests](#30-running-the-automated-tests)
31. [Performance](#31-performance)
32. [Security Considerations](#32-security-considerations)
33. [Known Limitations](#33-known-limitations)
34. [SpeedFace-V5L Compatibility](#34-speedface-v5l-compatibility)
35. [Read-Only Guarantee](#35-read-only-guarantee)
36. [Phase 3 Acceptance Checklist](#36-phase-3-acceptance-checklist)
37. [Troubleshooting](#37-troubleshooting)

---

## 1. What This Project Does

**Phase 1** proved that a free Python library can connect to the SpeedFace-V5L over
LAN (TCP port 4370) and read device info, users, and attendance records.

**Phase 2** built a reliable local synchronisation service that fetches attendance
data and stores it in a local SQLite database with full duplicate protection.

**Phase 3** adds a clean integration boundary between the device service and the
future Attendance Management System:

- Separates device communication, sync logic, and API concerns into distinct layers
- Exposes a secure REST API backed by the local SQLite database
- Adds normalized data models that hide ZKTeco protocol details from API consumers
- Supports an employee/device-user mapping structure (unmapped users are retained)
- Provides a background sync worker with configurable interval
- Enables the future Laravel system to consume attendance data without knowing anything
  about ZKTeco, port 4370, or device-specific formats

Laravel, MySQL, employee management, payroll, and reporting are **not part of Phases 1–3**.

---

## 2. Verified Device

| Field              | Value                        |
|--------------------|------------------------------|
| Manufacturer       | ZKTeco                       |
| Model (self-reported) | xFace600 / SpeedFace-V5L series |
| Firmware           | Ver 6.60 Aug 28 2020         |
| Platform           | ZAM180_TFT                   |
| IP Address         | 192.168.10.3 (your network)  |
| Port               | 4370 (TCP)                   |
| Users              | 97                           |
| Attendance Records | ~99,952 (99,918 stored locally) |
| Protocol           | ZKTeco proprietary binary/TCP |
| Verified           | August 2026                  |

---

## 3. Required Python Version

**Python 3.10 or higher** (Python 3.14.4 used in testing).

```powershell
python --version
```

---

## 4. Free / Open-Source Library

| Field      | Value                                       |
|------------|---------------------------------------------|
| Library    | **pyzk**                                    |
| Version    | 0.9                                         |
| PyPI       | https://pypi.org/project/pyzk/              |
| Repository | https://github.com/fananimi/pyzk            |
| License    | **MIT**                                     |
| Protocol   | ZKTeco binary over TCP (port 4370) or UDP   |

pyzk is an unofficial reverse-engineered implementation of the ZKTeco binary protocol.
It is not affiliated with or endorsed by ZKTeco.

**Only these pyzk methods are used (all read-only):**

| Method                      | Purpose                      |
|-----------------------------|------------------------------|
| `zk.connect()`              | Establish TCP connection      |
| `conn.disconnect()`         | Clean disconnect              |
| `conn.get_device_name()`    | Read device name              |
| `conn.get_serialnumber()`   | Read serial number            |
| `conn.get_firmware_version()` | Read firmware version       |
| `conn.get_platform()`       | Read platform string          |
| `conn.get_face_version()`   | Read face firmware version    |
| `conn.get_fp_version()`     | Read fingerprint version      |
| `conn.get_mac()`            | Read MAC address              |
| `conn.get_time()`           | Read device clock             |
| `conn.read_sizes()`         | Read capacity/usage counters  |
| `conn.get_users()`          | Read registered users         |
| `conn.get_attendance()`     | Read attendance records       |

No write, delete, clear, or modify methods are called. Ever.

---

## 5. Project Structure

```
speedface-integration/
│
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py        All REST endpoints — auth, pagination, filtering
│   │   ├── schemas.py       Pydantic response models (normalized, ZKTeco-free)
│   │   └── server.py        FastAPI app factory + lifespan handler
│   │
│   ├── config/
│   │   ├── __init__.py      Re-exports DeviceConfig for backward compatibility
│   │   ├── device_config.py Device connection settings (IP, port, key, timeout)
│   │   └── settings.py      Phase 3 settings (API_KEY, API_PORT, SYNC_INTERVAL)
│   │
│   ├── database.py          SQLite schema + all DB access functions
│   ├── device.py            pyzk wrapper — read-only ZK communication
│   ├── device_models.py     Normalized data models (ZKTeco-independent)
│   ├── logger_setup.py      Rotating file + console logging
│   ├── main.py              All CLI command handlers (Phase 1 + 2 + 3)
│   ├── sync_engine.py       Core sync logic (fetch, batch, dedup, state)
│   └── sync_service.py      SyncService with thread lock + background worker
│
├── data/
│   └── speedface.db         SQLite database (gitignored, created at runtime)
│
├── logs/
│   └── speedface.log        Rotating log file (gitignored, created at runtime)
│
├── tests/
│   ├── conftest.py          Shared fixtures, sample data factories
│   ├── test_api.py          Phase 3: API, auth, pagination, filtering (72 tests)
│   ├── test_database.py     Phase 2: database layer (24 tests)
│   └── test_sync_engine.py  Phase 2: sync engine (31 tests)
│
├── .env                     NOT committed — device + API credentials
├── .env.example             Committed — safe placeholder template
├── .gitignore
├── _run_tests.py            Convenience test runner
├── requirements.txt
├── README.md
└── run.py                   CLI entry point
```

---

## 6. Installation

### 6.1 Create a virtual environment

```powershell
cd speedface-integration
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the script:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 6.2 Install dependencies

```powershell
pip install -r requirements.txt
```

Installs:

| Package           | Version  | Purpose                           | License      |
|-------------------|----------|-----------------------------------|--------------|
| pyzk              | 0.9      | ZKTeco LAN/TCP communication      | MIT          |
| python-dotenv     | 1.0.1    | `.env` file loading               | BSD-3-Clause |
| fastapi           | 0.136.0  | REST API framework                | MIT          |
| uvicorn           | 0.32.1   | ASGI server                       | BSD-3-Clause |
| pydantic          | 2.13.4   | Data validation / response models | MIT          |
| APScheduler       | 3.10.4   | Background sync scheduler         | MIT          |
| pytest            | 8.3.5    | Test runner                       | MIT          |
| httpx             | 0.27.2   | API test client                   | BSD-3-Clause |

---

## 7. Configuration

### 7.1 Create `.env`

```powershell
Copy-Item .env.example .env
```

### 7.2 Edit `.env`

```env
# Device connection
DEVICE_IP=192.168.10.3
DEVICE_PORT=4370
DEVICE_COMM_KEY=0
DEVICE_TIMEOUT=10

# API server
API_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
API_HOST=127.0.0.1
API_PORT=8000
API_RELOAD=false

# Background worker
SYNC_INTERVAL_SECONDS=300
```

| Variable                | Description                                          | Default       |
|-------------------------|------------------------------------------------------|---------------|
| `DEVICE_IP`             | IPv4 address of SpeedFace on LAN                     | (required)    |
| `DEVICE_PORT`           | TCP port                                             | `4370`        |
| `DEVICE_COMM_KEY`       | Comm password (int; 0 = none)                        | `0`           |
| `DEVICE_TIMEOUT`        | Connection timeout in seconds                        | `10`          |
| `API_KEY`               | Bearer token for API auth — **never commit this**    | (required for serve) |
| `API_HOST`              | API bind address                                     | `127.0.0.1`   |
| `API_PORT`              | API port                                             | `8000`        |
| `API_RELOAD`            | Auto-reload in dev mode                              | `false`       |
| `SYNC_INTERVAL_SECONDS` | Background worker interval                           | `300`         |
| `DB_PATH`               | Override default SQLite path                         | `data/speedface.db` |

**IMPORTANT:** `.env` is gitignored and must never be committed.

---

## 8. Phase 1 — Device Commands

```powershell
# Verify TCP + ZK protocol handshake
python run.py test-connection

# Read device name, firmware, serial, time, counts
python run.py device-info

# List all registered users on the device
python run.py users

# List all attendance/transaction records
python run.py attendance

# Full 6-step compatibility diagnostic
python run.py diagnostics
```

---

## 9. Phase 2 — Synchronisation Commands

```powershell
# Fetch attendance records → store in local SQLite DB
python run.py sync

# Preview sync: show what would happen — no DB writes, no device changes
python run.py sync --dry-run

# Show current sync state from local database
python run.py sync-status

# Sync device users to local database
python run.py sync-users

# Re-read device metadata and update local database
python run.py refresh-device
```

---

## 10. Phase 3 — API Server and Worker Commands

### Generate an API key (one-time setup)

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output into `.env` as `API_KEY=<value>`.

### Start the API server

```powershell
python run.py serve
```

The API will be available at `http://127.0.0.1:8000`.
Interactive docs: `http://127.0.0.1:8000/docs`

```
================================================
  SpeedFace-V5L  —  API Server (Phase 3)
================================================

  API Host    : 127.0.0.1
  API Port    : 8000
  API Key     : Set
  Docs        : http://127.0.0.1:8000/docs
  API         : http://127.0.0.1:8000/api/health

  Press Ctrl+C to stop.
```

### Start the background sync worker

```powershell
python run.py worker
```

Runs a sync on the configured interval (default: every 5 minutes).
The worker connects to the device, fetches attendance records (read-only),
and stores new records in the local database. It never modifies the device.

### Append `--debug` to any command

```powershell
python run.py serve --debug
python run.py worker --debug
python run.py sync --debug
```

---

## 11. Phase 3 Architecture

```
                    SpeedFace-V5L
                    192.168.10.3:4370
                         │
                         │  LAN / TCP
                         │  READ ONLY
                         │  (get_attendance, get_users,
                         │   get_device_info only)
                         ▼
                ┌─────────────────────┐
                │   app/device.py     │  ← pyzk wrapper
                │   SpeedFaceDevice   │    read-only ZK comms
                └────────┬────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │  app/sync_engine.py │  ← fetch, batch, dedup,
                │  app/sync_service.py│    sync lock, state tracking
                └────────┬────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │  app/database.py    │  ← SQLite WAL
                │  data/speedface.db  │    5 tables + indexes
                └────────┬────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │  app/api/           │  ← FastAPI + Pydantic
                │  routes.py          │    Bearer auth
                │  schemas.py         │    Pagination + filtering
                └────────┬────────────┘
                         │  HTTP / JSON
                         ▼
                Future Laravel System
                (Phase 4 — not yet built)
```

Data always flows **from device → local DB → API**. Nothing flows back to the device.

---

## 12. Device Communication Layer

`app/device.py` — `SpeedFaceDevice`

Wraps pyzk. Exposes only read-only operations. Handles:
- TCP connection with timeout and retry
- Clean disconnect in `finally` blocks
- `ZKErrorConnection`, `ZKNetworkError`, socket timeout
- Returns normalized Python dicts — no pyzk objects leak out

`app/device_models.py` — `NormalizedAttendanceRecord`, `NormalizedUser`, `NormalizedDeviceInfo`

Converts raw device dicts into application-independent dataclasses:

```python
# Raw from device (pyzk)
{'user_id': '1001', 'timestamp': datetime(...), 'status': 0, 'punch': 10}

# Normalized
NormalizedAttendanceRecord(
    device_user_id    = '1001',
    punch_datetime    = '2026-08-13 08:00:00',
    punch_state       = 'check_in',       # human-readable string
    punch_state_raw   = 0,                # original device code preserved
    verification_type = 'face',           # human-readable string
    verification_type_raw = 10,           # original device code preserved
    raw_data          = '{"user_id":"1001","state_code":0,...}'
)
```

The future Laravel system sees `check_in` / `face` — not `0` / `10`.

---

## 13. Synchronisation Layer

`app/sync_engine.py` — Core sync logic (Phase 2, preserved intact)
`app/sync_service.py` — Phase 3 wrapper adding:

- **Thread-safe lock** preventing concurrent syncs
- **SyncWorker** — APScheduler-based background worker
- **Module-level singleton** shared by API server and worker

`SyncService` methods:

| Method              | Description                                      |
|---------------------|--------------------------------------------------|
| `sync_attendance()` | Fetch attendance from device → store locally     |
| `sync_users()`      | Fetch users from device → upsert locally         |
| `refresh_device()`  | Fetch device info → update devices table         |
| `get_status()`      | Return sync status from DB (no device connection)|
| `is_running()`      | Non-blocking check if sync is in progress        |

---

## 14. SQLite Data Layer

Database: `data/speedface.db`

### devices
One row per registered SpeedFace device. Supports multiple devices.

```sql
id, name, ip_address, port, serial_number, model,
firmware_version, platform, face_version, fp_version,
mac_address, user_count, attendance_count,
last_connected_at, last_sync_at, created_at, updated_at
UNIQUE (ip_address, port)
```

### device_users
Local copy of users registered on the device. Never pushed back.

```sql
id, device_id, device_uid, device_user_id, name,
privilege, card_number, created_at, updated_at
UNIQUE (device_id, device_user_id)
```

### attendance_records
Local copy of attendance transactions. Duplicate-protected.

```sql
id, device_id, device_user_id, punch_datetime,
punch_state, verification_type, raw_data, created_at
UNIQUE (device_id, device_user_id, punch_datetime, punch_state, verification_type)
INDEX  idx_att_device_datetime (device_id, punch_datetime)
INDEX  idx_att_user_id (device_id, device_user_id)
```

### device_employee_mapping
Maps device users to future application employees.
`employee_id` is NULL until the employee system is built.
Unmapped attendance is **never discarded**.

```sql
id, device_id, device_user_id,
employee_id,      -- NULL until employee system is implemented
mapping_status,   -- 'unmapped' | 'mapped' | 'ignored'
notes, created_at, updated_at
UNIQUE (device_id, device_user_id)
```

### sync_runs
One row per synchronisation attempt. Full audit trail.

```sql
id, device_id, started_at, completed_at,
status,           -- 'running' | 'success' | 'partial' | 'failed'
records_read, records_inserted, records_skipped, records_failed,
error_message, dry_run
```

### sync_state
Current sync checkpoint per device.

```sql
id, device_id,
last_successful_sync_at,
last_device_record_datetime,
last_sync_run_id,
updated_at
UNIQUE (device_id)
```

---

## 15. API Architecture

- Framework: **FastAPI 0.136** with Pydantic 2.13
- Server: **Uvicorn** (ASGI)
- Auth: **Bearer token** (HMAC constant-time comparison)
- Data source: **local SQLite only** — API never connects to the device directly
- All responses use a consistent JSON envelope

```
Laravel → GET /api/attendance?page=1 → FastAPI → SQLite → JSON response
                                          ↑
                               NOT to SpeedFace device
```

---

## 16. API Authentication

All endpoints except `GET /api/health` require:

```
Authorization: Bearer <API_KEY>
```

Set `API_KEY` in `.env`. Generate a secure value:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

| Response | Condition                              |
|----------|----------------------------------------|
| `200`    | Valid key                              |
| `401`    | Missing header, wrong scheme, bad key  |
| `503`    | `API_KEY` not configured on server     |

The key is compared using `hmac.compare_digest` to prevent timing attacks.
The key value is **never** logged.

---

## 17. API Endpoints

### GET /api/health
Liveness check. **No authentication required.**

```
GET /api/health
→ 200 {"status": "ok", "version": "3.0.0", "service": "speedface-integration"}
```

---

### GET /api/device
List all registered devices from local database.

```
GET /api/device
Authorization: Bearer <key>
→ 200 {"success": true, "data": [...]}
```

### GET /api/device/{id}
Single device details.

```
GET /api/device/1
→ 200 {"success": true, "data": {...}}
→ 404 if not found
```

---

### GET /api/sync/status
Current synchronisation status from local database. Does not connect to device.

```
GET /api/sync/status
→ 200 {
    "success": true,
    "data": {
        "device_found": true,
        "local_record_count": 99918,
        "last_sync_at": "2026-08-13 09:32:11",
        "last_sync_status": "success",
        "sync_in_progress": false,
        "last_run": {...}
    }
}
```

### GET /api/sync/history
Recent sync run records (non-dry-run only).

```
GET /api/sync/history?limit=10
```

### POST /api/sync
Trigger a read-only attendance fetch from the device.

- Returns **202 Accepted** immediately
- Sync runs in a background thread
- Returns **409 Conflict** if a sync is already running
- Never writes to the device

```
POST /api/sync
→ 202 {"success": true, "data": {"message": "Synchronisation started..."}}
→ 409 {"detail": {"code": "SYNC_IN_PROGRESS", "message": "..."}}
```

---

### GET /api/attendance
Paginated attendance records from local database.

```
GET /api/attendance
GET /api/attendance?page=2&per_page=50
GET /api/attendance?device_user_id=1001
GET /api/attendance?start_datetime=2026-08-13+00:00:00&end_datetime=2026-08-13+23:59:59
GET /api/attendance?device_id=1&device_user_id=1001&start_datetime=2026-08-01+00:00:00
```

---

### GET /api/device-users
Paginated device users from local database. Biometric templates are **never** returned.

```
GET /api/device-users
GET /api/device-users?device_id=1&page=1&per_page=50
```

---

## 18. Request / Response Examples

### Successful attendance response

```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "device_id": 1,
            "device_user_id": "1001",
            "punch_datetime": "2026-08-13 07:58:12",
            "punch_state": 0,
            "punch_state_label": "Check In",
            "verification_type": 10,
            "verification_type_label": "Face",
            "raw_data": "{\"user_id\": \"1001\", \"state_code\": 0, ...}",
            "created_at": "2026-08-13 09:32:11"
        }
    ],
    "meta": {
        "page": 1,
        "per_page": 100,
        "total": 99918,
        "pages": 1000
    }
}
```

### Authentication error

```json
{
    "detail": {
        "code": "UNAUTHORIZED",
        "message": "Invalid API credentials."
    }
}
```

### Sync in progress

```json
{
    "detail": {
        "code": "SYNC_IN_PROGRESS",
        "message": "A synchronisation is already running. Wait for it to complete."
    }
}
```

### Validation error (FastAPI 422)

```json
{
    "detail": [
        {
            "type": "less_than_equal",
            "loc": ["query", "per_page"],
            "msg": "Input should be less than or equal to 1000"
        }
    ]
}
```

---

## 19. Pagination

All list endpoints support:

| Parameter  | Default | Maximum | Description         |
|------------|---------|---------|---------------------|
| `page`     | `1`     | —       | Page number (1-based)|
| `per_page` | `100`   | `1000`  | Records per page     |

Response `meta` object:

```json
{
    "page": 1,
    "per_page": 100,
    "total": 99918,
    "pages": 1000
}
```

The API **never returns all 99,918 records in a single response**.
The future Laravel system should paginate through results.

---

## 20. Filtering

### Attendance filters

| Parameter        | Type   | Description                          |
|------------------|--------|--------------------------------------|
| `device_id`      | int    | Filter by device ID                  |
| `device_user_id` | string | Filter by device user ID             |
| `start_datetime` | string | `YYYY-MM-DD HH:MM:SS` — inclusive    |
| `end_datetime`   | string | `YYYY-MM-DD HH:MM:SS` — inclusive    |

Example:
```
GET /api/attendance?device_user_id=1001&start_datetime=2026-08-01+00:00:00&end_datetime=2026-08-31+23:59:59
```

Filters do **not** perform attendance calculations. No late/overtime/absence logic.
That belongs to a future phase.

### Device user filters

| Parameter   | Type | Description          |
|-------------|------|----------------------|
| `device_id` | int  | Filter by device ID  |

---

## 21. Sync Process

### Initial sync

```
python run.py sync
```

1. Init DB schema (CREATE IF NOT EXISTS — safe to repeat)
2. Connect to device (retry up to 3 times)
3. Read device info → upsert `devices` table
4. Create `sync_runs` row (`status='running'`)
5. Read ALL attendance records via `get_attendance()`
6. **Disconnect from device immediately** — DB work happens after
7. Process records in batches of 1,000 using `INSERT OR IGNORE`
8. Commit each batch — partial progress is preserved on interruption
9. Update `sync_runs` → `status='success'`
10. Update `sync_state` checkpoint
11. Print summary with device safety snapshot

### Subsequent syncs

Identical flow. `INSERT OR IGNORE` silently skips already-stored records.

### Background worker

```
python run.py worker
```

Repeats the sync on `SYNC_INTERVAL_SECONDS` (default 300s).
The API server and worker share the same `SyncService` singleton and lock —
they cannot run simultaneously.

---

## 22. Duplicate Detection Strategy

**Method:** `UNIQUE` constraint + `INSERT OR IGNORE`

**Unique key per record:**
```
(device_id, device_user_id, punch_datetime, punch_state, verification_type)
```

**Guarantee:** Running sync any number of times produces exactly the same local
record set. Verified by automated tests.

**Limitation:** Two punches by the same user within the same second with identical
state and verification type produce only one local record. Extremely unlikely in
normal device operation.

---

## 23. Incremental Synchronisation Strategy

**Protocol limitation:** `get_attendance()` always returns the full device history.
No timestamp or ID filter is supported by pyzk / SpeedFace-V5L protocol.

**Strategy:** Fetch all → deduplicate locally via `INSERT OR IGNORE`.

```
Sync #1 — 99,952 records read → 99,952 inserted
Sync #2 — 99,952 records read → 0 inserted, 99,952 skipped
New punch on device
Sync #3 — 99,953 records read → 1 inserted, 99,952 skipped
```

Transfer time scales with total device history (~102s for ~99,952 records).

---

## 24. Retry Behaviour

| Attempt | Action          |
|---------|-----------------|
| 1       | Connect         |
| —       | Wait 5 seconds  |
| 2       | Retry           |
| —       | Wait 10 seconds |
| 3       | Final retry     |
| —       | Fail with error |

- Maximum 3 attempts (configurable via `SyncConfig`)
- Does not retry indefinitely
- Each retry logged at WARNING level

---

## 25. Concurrent Sync Lock

A `threading.Lock` prevents two sync operations from running simultaneously.

```
API POST /api/sync → SyncService.is_running() → True?
    → 409 SYNC_IN_PROGRESS (immediate)

Background worker tick → lock already held?
    → SyncInProgressError logged, tick skipped
```

Tested by `TestConcurrentSyncLock` — including a two-thread race condition test.

---

## 26. Error Handling

| Situation                  | Behaviour                                            |
|----------------------------|------------------------------------------------------|
| Device offline             | Retry 3 times, then fail with clear message          |
| TCP timeout                | Retry, report cause                                  |
| Comm key mismatch          | Report auth error                                    |
| Attendance returns empty   | Warn about known SpeedFace-V5L firmware issue        |
| DB batch error             | Roll back batch, continue, `status=partial`          |
| Sync interrupted           | Committed batches survive; next sync deduplicates    |
| Invalid API key            | 401 (never logs key value)                           |
| API_KEY not configured     | 503 (safe failure)                                   |
| Device write endpoint      | 404/405 (does not exist)                             |
| Unhandled server exception | 500 with generic message (no traceback to client)    |

---

## 27. Multi-Device Architecture

The schema and API are designed for multiple devices from the start:

- Every table uses `device_id` as a foreign key
- `devices` table has `UNIQUE (ip_address, port)` — each device has one row
- Attendance and user queries can be filtered by `device_id`
- The current `.env` configures one device; Phase 4 can add a device management UI

```sql
-- Example: two devices
devices
  id=1  ip=192.168.10.3  name='Branch A — SpeedFace'
  id=2  ip=192.168.10.4  name='Branch B — SpeedFace'
```

The IP `192.168.10.3` is not hard-coded anywhere in the source — it exists only
in `.env` and the `devices` table.

---

## 28. Employee / Device User Mapping

The `device_employee_mapping` table decouples device users from application employees:

```
Device User 1001
      ↓
device_employee_mapping (employee_id=NULL, status='unmapped')
      ↓
Future Employee #25 (when HR system is implemented)
```

**Unmapped attendance is never discarded.** Records for unmapped users are stored
normally. The mapping status (`unmapped`, `mapped`, `ignored`) is tracked separately.

```
GET /api/attendance?device_user_id=1001
→ Returns records regardless of mapping status
```

---

## 29. Device Safety Verification

Every `sync` run prints a before/after snapshot:

```
  ── Device Safety Snapshot ───────────────────────
  Users (before/after)        : 97 / 97
  Attendance (before/after)   : 99,952 / 99,952
  [OK] Device counts are unchanged.
```

### Final mandatory test procedure

```
1. Record device state:    Users=97  Attendance=99,952
2. python run.py sync      → records stored locally
3. python run.py device-info  → Users=97  Attendance=99,952 (unchanged)
4. python run.py sync      → 0 new, all skipped
5. Make one test punch on the device
6. python run.py sync      → exactly 1 new record inserted
7. python run.py device-info  → Users=97  Attendance=99,953 (one new punch only)
```

---

## 30. Running the Automated Tests

**127 tests** covering Phase 1 database layer, Phase 2 sync engine, and Phase 3 API.
No real device or network required — all device communication is mocked.

```powershell
# With venv active:
python _run_tests.py

# Or directly:
python -m pytest tests/ -v --tb=short
```

### Test suite breakdown

| File                  | Tests | Coverage                                                  |
|-----------------------|-------|-----------------------------------------------------------|
| `test_api.py`         | 72    | Auth, health, devices, attendance pagination/filtering, device-users, sync status/history/trigger, concurrent lock, read-only verification, normalized models, Phase 3 DB |
| `test_database.py`    | 24    | Schema, device upsert, user upsert, attendance dedup, dry-run, sync_runs, sync_state, helper queries |
| `test_sync_engine.py` | 31    | Full sync, duplicate protection, incremental, dry-run, retry, partial failure, user sync, refresh device, safety, integrity |

Expected result:
```
127 passed in ~6s
```

---

## 31. Performance

| Metric              | Value (Phase 1 measurement)  |
|---------------------|------------------------------|
| Records read        | ~99,952                      |
| Read duration       | ~102 seconds                 |
| Throughput          | ~980 records/second          |
| Connection time     | 131–162 ms                   |
| DB insert (99,918)  | Negligible vs network time   |

The API serves pre-synchronized data from SQLite — response times are
milliseconds regardless of how many records exist in the database.

---

## 32. Security Considerations

- `.env` is gitignored — never committed
- `API_KEY` is not logged at any level
- `DEVICE_COMM_KEY` is not logged at any level
- Passwords and biometric templates are never stored or returned
- API key comparison uses `hmac.compare_digest` (constant-time)
- Input parameters (datetime, device_id, pagination) are validated
- The API binds to `127.0.0.1` by default — LAN access requires explicit `API_HOST=0.0.0.0`
- The system is designed for **LAN use only** — do not expose to the public internet
- No pyzk write/delete/clear method is called anywhere in the codebase

---

## 33. Known Limitations

1. **No true incremental retrieval** — pyzk fetches the full attendance history every sync.
   ~102 seconds per sync for ~99,952 records. Transfer time grows with device history.

2. **Attendance may be empty on some SpeedFace-V5L firmware** — `GET_FREE_SIZES` returns
   a single DWORD on some firmware versions. The ZAM180_TFT platform tested does not
   exhibit this. If it occurs, a detailed warning is shown.

3. **Same-second duplicate punch limitation** — if the same user punches twice in the
   same second with identical state and verification type, only one record is stored.

4. **pyzk is unofficial** — reverse-engineered, not endorsed by ZKTeco.

5. **Single connection at a time** — the device may reject a second connection while
   one is open. The engine always disconnects in `finally` blocks.

6. **SQLite only in Phase 3** — migration to MySQL/MariaDB is a Phase 4 concern.

7. **No live capture** — real-time event streaming is deferred to a future phase.

8. **httpx deprecation warning** — FastAPI's TestClient uses `starlette.testclient` which
   suggests migrating to `httpx2`. Tests pass; this is a cosmetic warning only.

---

## 34. SpeedFace-V5L Compatibility

| Check                         | Status        | Notes                                        |
|-------------------------------|---------------|----------------------------------------------|
| TCP port 4370 reachable       | **VERIFIED**  | Phase 1, August 2026                         |
| ZK protocol handshake         | **VERIFIED**  | 131–162 ms                                   |
| Device info retrieval         | **VERIFIED**  | fw=Ver 6.60 Aug 28 2020, platform=ZAM180_TFT |
| User retrieval                | **VERIFIED**  | 97 users                                     |
| Attendance retrieval          | **VERIFIED**  | 99,918 records stored locally                |
| Duplicate prevention          | **VERIFIED**  | 127 automated tests pass                     |
| Device data unchanged         | **VERIFIED**  | Counts identical before/after all syncs      |
| REST API serving data         | **VERIFIED**  | FastAPI + SQLite                             |
| Concurrent sync lock          | **VERIFIED**  | Thread-race test passes                      |

**Library:** pyzk 0.9 — MIT — https://github.com/fananimi/pyzk

---

## 35. Read-Only Guarantee

> The SpeedFace-V5L is used exclusively as a read-only source of attendance and
> device data. The synchronisation/API layer does not modify or delete data on the device.

The following device operations are **absolutely prohibited** and are not implemented:

```
clear_attendance()   delete_user()       set_user()
clear_data()         clear_admin()       restart()
poweroff()           set_time()          delete_user_template()
save_user_template() HR_save_usertemplates()  enroll_user()
```

Verified by `TestDeviceReadOnly::test_sync_service_does_not_call_write_methods`
and `TestDeviceReadOnly::test_no_device_write_endpoints_exist`.

---

## 36. Phase 3 Acceptance Checklist

```
[x] Phase 1 functionality still works
[x] Phase 2 functionality still works
[x] Device communication isolated from business logic (app/device.py ← only layer touching ZK)
[x] Synchronisation service separated from device communication (app/sync_service.py)
[x] SQLite remains the Phase 3 local data store
[x] Normalized attendance records available (app/device_models.py)
[x] Raw device data preserved in raw_data field
[x] Device user mapping structure exists (device_employee_mapping table)
[x] Unmapped users are retained (never discarded)
[x] REST API implemented (FastAPI)
[x] API authentication works (Bearer token, constant-time compare)
[x] API pagination works (page/per_page, meta in response)
[x] API filtering works (device_id, device_user_id, start/end datetime)
[x] Device status endpoint works (GET /api/device)
[x] Synchronisation status endpoint works (GET /api/sync/status)
[x] Attendance endpoint works (GET /api/attendance)
[x] Device users endpoint works (GET /api/device-users)
[x] Sync trigger endpoint works (POST /api/sync → 202)
[x] Concurrent synchronisation prevented (409 SYNC_IN_PROGRESS)
[x] Retry/error handling works (3 attempts, backoff)
[x] Multi-device architecture supported (device_id FK throughout)
[x] Logging works (console + rotating file)
[x] Audit/sync history works (sync_runs table + GET /api/sync/history)
[x] 127 automated tests pass
[x] Device remains completely READ-ONLY
[x] No device records deleted
[x] No device records cleared
[x] No device records modified
[x] Documentation complete
```

---

## 37. Troubleshooting

### "DEVICE_IP is not set"
```powershell
Copy-Item .env.example .env
# Edit .env — set DEVICE_IP
```

### "API_KEY is not set"
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
# Copy output → .env API_KEY=<value>
```

### API returns 503 API_KEY_NOT_CONFIGURED
`API_KEY` is missing from `.env`. Add it before starting `python run.py serve`.

### API returns 401 on every request
Check the `Authorization` header format: `Bearer <your-key>` (exact key from `.env`).

### "Connection timed out"
- `ping 192.168.10.3` — is the device on the network?
- Port 4370 must be open (no firewall blocking)
- Device menu → Comm → Ethernet — TCP enabled?
- Try `DEVICE_TIMEOUT=30`

### sync shows 0 new records after first run
Working correctly — all records already stored. Run `python run.py sync-status` to confirm.
To force a full re-import: delete `data/speedface.db` (local data only — device untouched).

### Worker exits immediately
Check `SYNC_INTERVAL_SECONDS` is >= 10. Check `DEVICE_IP` is set.

### PowerShell script execution blocked
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
