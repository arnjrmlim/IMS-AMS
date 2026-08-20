# IMS-AMS — Attendance Management System

A two-component system for capturing, synchronising, and managing attendance data from a **ZKTeco SpeedFace-V5L** biometric device.

---

## Repository Structure

```
IMS-AMS/
├── speedface-integration/   Python REST API service (Phases 1–3)
└── attendance-system/       Laravel web application (Phase 4)
```

---

## System Overview

```
SpeedFace-V5L (192.168.10.3:4370)
        │  LAN / TCP — READ ONLY
        ▼
speedface-integration/       ← Python + FastAPI + SQLite
        │  REST API (http://127.0.0.1:8000/api)
        ▼
attendance-system/           ← Laravel 12 + MySQL
        │  Eloquent ORM
        ▼
Browser (Bootstrap 5)
```

The SpeedFace device is **read-only throughout the entire system**. No data is ever written, modified, or deleted on the device.

---

## Components

### speedface-integration (Python)

Communicates directly with the SpeedFace-V5L over LAN, syncs attendance data to a local SQLite database, and exposes it via a secure REST API.

- **Stack:** Python 3.10+, FastAPI, pyzk, SQLite, APScheduler
- **127 automated tests**
- [Full documentation](speedface-integration/README.md)

### attendance-system (Laravel)

Web application that consumes the Python REST API to display and manage attendance records.

- **Stack:** Laravel 12, PHP 8.2, MySQL/MariaDB, Bootstrap 5
- **43 automated tests, 92 assertions**
- [Full documentation](attendance-system/README.md)

---

## Quick Start

### 1. Start the Python Integration Service

```powershell
cd speedface-integration
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then edit .env with your device IP and API key
python run.py serve
# API running at http://127.0.0.1:8000
```

### 2. Start the Laravel Application

```powershell
cd attendance-system
composer install
Copy-Item .env.example .env   # then edit .env with DB credentials and API key
php artisan key:generate
php artisan migrate
php artisan db:seed
php artisan serve --port=8001
# App running at http://127.0.0.1:8001
```

### 3. Log in

Open `http://127.0.0.1:8001` and log in with:
- **Username:** `admin`
- **Password:** `Admin@1234`

Change your password after first login.

---

## Requirements

| Component              | Requirement                  |
|------------------------|------------------------------|
| Python                 | 3.10+                        |
| PHP                    | 8.2+                         |
| Composer               | 2.x                          |
| MySQL / MariaDB        | 10.4+ (XAMPP)                |
| SpeedFace-V5L          | Reachable on LAN at port 4370 |

---

## Security Notes

- `.env` files are gitignored and must never be committed
- The `SPEEDFACE_API_KEY` is never sent to the browser — all API calls are server-side only
- The SpeedFace device is READ-ONLY by design and policy
