# Head Office Attendance System — Phase 4

A Laravel 12 web application that consumes synchronized attendance data from the
**SpeedFace-V5L biometric device** via the Phase 3 Python Integration Service.

> **Device Policy — Non-Negotiable:**
> The SpeedFace-V5L is **READ-ONLY** throughout all phases.
> This Laravel application never communicates directly with the device.
> All device data is consumed through the Python REST API.

---

## System Architecture

```
SpeedFace-V5L (192.168.10.3:4370)
        │
        │  LAN / TCP — READ ONLY
        │  pyzk library (MIT)
        ▼
Python Integration Service       ← Phase 1, 2, 3
(speedface-integration/)
        │
        │  REST API — Bearer auth
        │  http://127.0.0.1:8000/api
        ▼
Laravel Application              ← Phase 4 (this project)
(attendance-system/)
        │
        │  Eloquent ORM
        ▼
MySQL / MariaDB
(headoffice_attendance)
        │
        ▼
Browser (Bootstrap 5)
```

**Data flow direction:**
```
SpeedFace → Python Service → Python SQLite → Python API → Laravel → MySQL → Browser
```

Nothing flows back to the SpeedFace device. Ever.

---

## Technology Stack

| Component          | Version    | Notes                                   |
|--------------------|------------|-----------------------------------------|
| PHP                | 8.2.12     | XAMPP                                   |
| Laravel Framework  | 12.66.0    | Latest compatible with PHP 8.2          |
| Composer           | 2.10.2     |                                         |
| MariaDB            | 10.4.32    | XAMPP                                   |
| Bootstrap          | 5.3.3      | CDN — no Node/npm required              |
| Bootstrap Icons    | 1.11.3     | CDN                                     |
| PHPUnit            | 11.x       | Included with Laravel                   |

---

## Prerequisites

Before running the Laravel application, you need:

1. **XAMPP** running (Apache optional, MySQL/MariaDB required)
2. **PHP 8.2+** in your PATH (`C:\xampp\php`)
3. **Composer 2.x** installed
4. **Python Integration Service** (Phase 3) running:
   ```powershell
   cd C:\Projects\test\speedface-integration
   .\venv\Scripts\Activate.ps1
   python run.py serve
   ```
   The Python API must be running on `http://127.0.0.1:8000` before using the
   Dashboard, Devices, Sync, and Attendance pages.

---

## Installation

### 1. Navigate to project directory

```powershell
cd C:\Projects\test\attendance-system
```

### 2. Install PHP dependencies

```powershell
composer install
```

### 3. Create the `.env` file

```powershell
Copy-Item .env.example .env
php artisan key:generate
```

Then edit `.env` with your settings (see [Configuration](#configuration) below).

### 4. Create the database

In MySQL / MariaDB:
```sql
CREATE DATABASE headoffice_attendance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Or via XAMPP shell:
```powershell
& "C:\xampp\mysql\bin\mysql.exe" -u root -e "CREATE DATABASE IF NOT EXISTS headoffice_attendance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 5. Run migrations

```powershell
php artisan migrate
```

### 6. Seed roles, permissions, and administrator

```powershell
php artisan db:seed
```

Output:
```
Administrator ready — username: admin
Change the password after first login!
```

### 7. Start the development server

```powershell
php artisan serve --port=8001
```

Application URL: `http://127.0.0.1:8001`

---

## Configuration

All sensitive configuration lives in `.env` — never committed to Git.

### Application

```env
APP_NAME="Head Office Attendance System"
APP_URL=http://127.0.0.1:8001
APP_TIMEZONE=Asia/Manila
APP_DEBUG=true          # set false in production
```

### Database

```env
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=headoffice_attendance
DB_USERNAME=root
DB_PASSWORD=
```

### SpeedFace Integration Service

```env
# URL of the Phase 3 Python API
SPEEDFACE_API_URL=http://127.0.0.1:8000/api

# Bearer token — must match API_KEY in speedface-integration/.env
# NEVER expose this to the browser or JavaScript
SPEEDFACE_API_KEY=<your-key-here>

# HTTP timeout in seconds
SPEEDFACE_API_TIMEOUT=30
```

The `SPEEDFACE_API_KEY` must match the `API_KEY` value in
`C:\Projects\test\speedface-integration\.env`.

### Initial Administrator (seeder)

```env
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=Admin@1234
INITIAL_ADMIN_NAME="System Administrator"
INITIAL_ADMIN_EMAIL=admin@headoffice.local
```

Change the password after first login. These values are only used by
`php artisan db:seed` and are safe to change before seeding.

---

## First Login

1. Start XAMPP (MySQL)
2. Start the Python Integration Service (`python run.py serve`)
3. Start Laravel (`php artisan serve --port=8001`)
4. Open `http://127.0.0.1:8001`
5. Login with:
   - **Username:** `admin`
   - **Password:** `Admin@1234`
6. Change your password after first login.

---

## Available Commands

### Laravel (run from `attendance-system/`)

```powershell
# Start development server (port 8001 — frees 8000 for Python API)
php artisan serve --port=8001

# Run all migrations fresh with seed data
php artisan migrate:fresh --seed

# Run migrations only
php artisan migrate

# Seed roles, permissions, admin user
php artisan db:seed

# Run automated tests
php artisan test

# Check Python Integration Service health
php artisan speedface:health

# Trigger attendance synchronisation via Python API
# (Laravel → Python API → SpeedFace READ ONLY)
php artisan speedface:sync

# Clear all caches
php artisan config:clear
php artisan cache:clear
```

### Python Integration Service (run from `speedface-integration/`)

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Start the REST API server (required for Laravel to function)
python run.py serve

# Start the background auto-sync worker
python run.py worker

# Manual sync
python run.py sync

# Check sync status
python run.py sync-status

# Diagnostics
python run.py diagnostics
```

---

## Database Schema

### Tables

| Table                  | Purpose                                              |
|------------------------|------------------------------------------------------|
| `users`                | Application login accounts (username + password)     |
| `roles`                | Administrator, HR, Supervisor, Employee              |
| `permissions`          | 17 granular permission slugs                         |
| `role_user`            | Many-to-many: users ↔ roles                          |
| `permission_role`      | Many-to-many: roles ↔ permissions                    |
| `branches`             | Organisation branches (foundation)                   |
| `departments`          | Departments linked to branches                       |
| `employees`            | Employee records (foundation — no payroll/leave yet) |
| `devices`              | Local copy of SpeedFace device info                  |
| `device_user_mappings` | Maps SpeedFace user IDs to employees                 |
| `attendance_records`   | Local copy of synced punch transactions              |
| `sync_runs`            | Audit trail of every sync attempt                    |
| `audit_logs`           | Application action log (logins, syncs, etc.)         |
| `system_settings`      | Key/value application settings                       |
| `sessions`             | PHP session storage                                  |
| `cache`                | File-based cache (configured in .env)                |
| `jobs`                 | Queue jobs (for future use)                          |

### Attendance records — duplicate protection

```sql
UNIQUE (device_id, device_user_id, punch_datetime, punch_state, verification_type)
```

This mirrors the Phase 3 Python service's own constraint exactly, ensuring
duplicates cannot be created from either side.

### Device user mapping

`device_user_id` is the string identifier from the SpeedFace device.
It is **not** assumed to equal any application employee ID.
`employee_id` is nullable — unmapped attendance is retained, never discarded.

---

## Application Modules

### Dashboard
- Integration service online/offline status (live health check)
- Device count, online devices, employee count, attendance record count
- Last sync date/time and status
- Quick links to Devices and Sync

### Devices
- List all registered SpeedFace devices
- Device detail: firmware, platform, serial, IP, user/attendance counts
- Refresh status button (calls Python API → no direct device contact)
- Sync history per device

### Synchronisation
- Current sync status from Python API
- Manual **Sync Now** button (AJAX, with loading state and result display)
- Polling — automatically detects when sync completes
- Local sync run history table
- Device safety panel explaining READ-ONLY guarantee

### Attendance Records
- Paginated attendance records from Python API (default 25/page)
- Filters: device, device user ID, date from, date to
- Displays: date, time, device user ID, punch state (Check In/Out), verification type
- No business calculations — raw punch data only

### Employees (Foundation)
- List with search by name, filter by branch/department
- Employee detail with device mapping status
- Full HR management deferred to Phase 5

---

## Authentication

- Login identifier: **username** (not email)
- Password hashing: Laravel's bcrypt (`BCRYPT_ROUNDS=12`)
- Rate limiting: 6 attempts per minute per IP
- Session driver: file (no Redis required)
- Inactive users: blocked at middleware level (logged out, shown message)
- CSRF protection: enabled on all forms
- Audit log: every login and logout is recorded

### Roles and Permissions

| Role          | Key Permissions                                              |
|---------------|--------------------------------------------------------------|
| Administrator | All permissions                                              |
| HR            | View/manage employees, view/run sync, view attendance        |
| Supervisor    | View employees, view attendance, view devices                |
| Employee      | View dashboard only                                          |

---

## Python API Integration

The `SpeedFaceApiService` (`app/Services/SpeedFaceApiService.php`) handles all
communication with the Python Integration Service.

```
Browser → Laravel Controller → SpeedFaceApiService → Python API
```

**The API key is never sent to the browser.** All Python API calls are
server-side only.

### Endpoints consumed

| Method | Endpoint            | Used by                        |
|--------|---------------------|--------------------------------|
| GET    | `/api/health`       | Dashboard, all pages (status)  |
| GET    | `/api/device`       | Devices list                   |
| GET    | `/api/device/{id}`  | Device detail, refresh         |
| GET    | `/api/sync/status`  | Dashboard, Sync page, polling  |
| GET    | `/api/sync/history` | Sync page history              |
| POST   | `/api/sync`         | Sync Now button, Artisan sync  |
| GET    | `/api/attendance`   | Attendance records page        |
| GET    | `/api/device-users` | (available, used in mapping)   |

### API failure handling

If the Python service is offline:
- Dashboard shows an offline banner
- Devices page shows stale local data
- Sync page shows offline warning
- Attendance page shows "Integration service is offline" message
- No stack traces, API keys, or internal paths are shown to users

---

## Automated Tests

**43 tests, 92 assertions** — all pass.

```powershell
php artisan test
```

### Test coverage

| Test Class                   | Tests | Coverage                                              |
|------------------------------|-------|-------------------------------------------------------|
| `AuthenticationTest`         | 14    | Login (valid/invalid/missing), logout, middleware, inactive user, permissions |
| `AttendanceTest`             | 9     | Page load, offline message, pagination, filter, duplicate prevention, unmapped users |
| `SpeedFaceApiServiceTest`    | 10    | Health, devices, sync status, trigger (202/409/offline), attendance filters |
| `SynchronizationTest`        | 8     | Sync page, offline banner, trigger, 409, 503, unauthenticated, status poll |
| `ExampleTest`                | 1     | Root redirect                                         |
| `Unit\ExampleTest`           | 1     | Baseline                                              |

Tests use:
- SQLite in-memory database (`DB_CONNECTION=sqlite`, `DB_DATABASE=:memory:`)
- `Http::fake()` for all Python API calls (no real network connections)
- `RefreshDatabase` — each test starts with a clean database

---

## Known Limitations (Phase 4)

The following are intentionally **not implemented** in Phase 4:

- Attendance calculations (late, overtime, undertime, absent, present)
- Shift schedules and rules
- Leave management
- Payroll
- Email notifications
- Automatic backup
- Branch/Department management UI (models exist, full CRUD deferred)
- User management UI (roles assigned by seeder only)
- Employee creation UI (display and mapping only)
- Device write operations (by design — device is READ-ONLY)
- Multi-device branch assignment UI (schema supports it, UI deferred)

These belong to Phases 5–7.

---

## Project Structure

```
attendance-system/
├── app/
│   ├── Console/Commands/
│   │   ├── SpeedFaceHealth.php    php artisan speedface:health
│   │   └── SpeedFaceSync.php      php artisan speedface:sync
│   ├── Http/
│   │   ├── Controllers/
│   │   │   ├── Auth/LoginController.php
│   │   │   ├── AttendanceController.php
│   │   │   ├── DashboardController.php
│   │   │   ├── DeviceController.php
│   │   │   ├── EmployeeController.php
│   │   │   └── SynchronizationController.php
│   │   └── Middleware/
│   │       ├── CheckActive.php    Block inactive users
│   │       └── CheckPermission.php  permission:slug middleware
│   ├── Models/
│   │   ├── User.php, Role.php, Permission.php
│   │   ├── Branch.php, Department.php, Employee.php
│   │   ├── Device.php, DeviceUserMapping.php
│   │   ├── AttendanceRecord.php, SyncRun.php
│   │   ├── AuditLog.php, SystemSetting.php
│   ├── Providers/AppServiceProvider.php   Gate definitions
│   └── Services/
│       ├── SpeedFaceApiService.php   Python API client
│       └── AuditService.php
├── database/
│   ├── factories/ UserFactory.php, DeviceFactory.php
│   ├── migrations/ (12 domain migrations)
│   └── seeders/
│       ├── RolesAndPermissionsSeeder.php
│       ├── SystemSettingsSeeder.php
│       └── AdminUserSeeder.php
├── resources/views/
│   ├── auth/login.blade.php
│   ├── layouts/app.blade.php       Bootstrap 5, responsive sidebar
│   ├── dashboard/index.blade.php
│   ├── devices/index.blade.php, show.blade.php
│   ├── sync/index.blade.php
│   ├── attendance/index.blade.php
│   ├── employees/index.blade.php, show.blade.php
│   └── errors/ 404, 403, 419, 429, 500, 503
├── routes/web.php
├── tests/Feature/
│   ├── AuthenticationTest.php
│   ├── AttendanceTest.php
│   ├── SpeedFaceApiServiceTest.php
│   └── SynchronizationTest.php
└── .env.example
```

---

## Phase 4 Acceptance Checklist

```
[x] Laravel application runs successfully
[x] Laravel connects to MySQL/MariaDB (headoffice_attendance)
[x] Database migrations work (php artisan migrate)
[x] Seed process works (php artisan db:seed)
[x] Username/password authentication works
[x] Administrator account can log in (admin / Admin@1234)
[x] Logout works and session is invalidated
[x] Authentication middleware protects all routes
[x] Inactive user middleware blocks deactivated accounts
[x] Role foundation exists (4 roles seeded)
[x] Permission foundation exists (17 permissions, Gate-registered)
[x] Application layout implemented (Bootstrap 5, responsive sidebar)
[x] Sidebar navigation works with @can permission checks
[x] Dashboard works (device status, sync status, record counts)
[x] Device module works (list, detail)
[x] Device refresh calls Python API (not device directly)
[x] Python API connection works (SpeedFaceApiService)
[x] Python API authentication works (Bearer token, server-side only)
[x] API timeout configured (30s default)
[x] API failures handled gracefully (offline banners, no stack traces)
[x] Synchronisation page works
[x] Sync status displayed from Python API
[x] Manual Sync Now works (AJAX, progress indicator, result display)
[x] Concurrent sync protection (409 from Python API handled)
[x] Attendance records displayed (paginated)
[x] Attendance filtering works (device, user ID, date range)
[x] Device user mapping foundation exists
[x] Employee foundation exists (models, migrations, read-only UI)
[x] Branch and department foundation exists
[x] Sync history recorded in sync_runs table
[x] Audit logging exists (login, logout, sync triggered)
[x] System settings foundation exists
[x] Timezone configured (Asia/Manila)
[x] Error pages work (404, 403, 419, 429, 500, 503)
[x] Input validation works (date format, per_page range)
[x] 43 automated tests pass (92 assertions)
[x] Duplicate attendance records prevented (DB UNIQUE constraint)
[x] Unmapped device users retained (employee_id nullable)
[x] Multi-device architecture supported (device_id FK throughout)
[x] No Laravel code communicates directly with SpeedFace
[x] No Phase 4 feature modifies SpeedFace data
[x] Existing Phase 1–3 functionality remains operational
[x] Documentation complete
```

---

## Running Both Services Together

Open two PowerShell terminals:

**Terminal 1 — Python Integration Service:**
```powershell
cd C:\Projects\test\speedface-integration
.\venv\Scripts\Activate.ps1
python run.py serve
# API running at http://127.0.0.1:8000
```

**Terminal 2 — Laravel Application:**
```powershell
cd C:\Projects\test\attendance-system
php artisan serve --port=8001
# App running at http://127.0.0.1:8001
```

Then open `http://127.0.0.1:8001` and log in with `admin` / `Admin@1234`.

---

## Security Notes

- `.env` is gitignored — never committed
- `SPEEDFACE_API_KEY` is never sent to the browser
- Passwords are hashed with bcrypt (12 rounds)
- CSRF protection on all forms
- Rate limiting on login (6 attempts/minute)
- Input validation on all controller actions
- No stack traces in production (`APP_DEBUG=false`)
- Audit log records all authentication events
- Inactive users are blocked even if session token exists
