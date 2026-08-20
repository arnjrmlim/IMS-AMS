<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Dashboard') — {{ config('app.name') }}</title>

    {{-- Bootstrap 5 CDN --}}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    {{-- Bootstrap Icons CDN --}}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

    <style>
        :root {
            --sidebar-width: 260px;
            --sidebar-bg: #1e2a3a;
            --sidebar-hover: #2d3f54;
            --sidebar-active: #0d6efd;
            --header-height: 56px;
        }
        body { background: #f4f6f9; font-size: 0.9rem; }

        /* Sidebar */
        #sidebar {
            position: fixed; top: 0; left: 0; bottom: 0;
            width: var(--sidebar-width);
            background: var(--sidebar-bg);
            z-index: 1040; overflow-y: auto;
            transition: transform .25s ease;
        }
        #sidebar .sidebar-brand {
            padding: 1rem 1.25rem;
            border-bottom: 1px solid rgba(255,255,255,.08);
            color: #fff; font-weight: 700; font-size: .95rem;
            line-height: 1.3;
        }
        #sidebar .nav-link {
            color: rgba(255,255,255,.7); padding: .45rem 1.25rem;
            border-radius: .25rem; margin: 1px .5rem;
            display: flex; align-items: center; gap: .5rem;
            transition: background .15s, color .15s;
        }
        #sidebar .nav-link:hover        { background: var(--sidebar-hover); color: #fff; }
        #sidebar .nav-link.active       { background: var(--sidebar-active); color: #fff; }
        #sidebar .nav-section {
            font-size: .7rem; letter-spacing: .08em;
            text-transform: uppercase; color: rgba(255,255,255,.35);
            padding: .75rem 1.5rem .25rem;
        }

        /* Main */
        #main-content {
            margin-left: var(--sidebar-width);
            min-height: 100vh;
            display: flex; flex-direction: column;
        }
        #topbar {
            height: var(--header-height);
            background: #fff;
            border-bottom: 1px solid #dee2e6;
            position: sticky; top: 0; z-index: 1030;
            padding: 0 1.5rem;
            display: flex; align-items: center; justify-content: space-between;
        }
        .page-content { flex: 1; padding: 1.5rem; }

        /* Status badges */
        .badge-online  { background: #198754; }
        .badge-offline { background: #dc3545; }
        .badge-unknown { background: #6c757d; }

        /* Alert strip for offline warning */
        .api-offline-banner {
            background: #fff3cd; border: 1px solid #ffc107;
            border-radius: .375rem; padding: .6rem 1rem;
            color: #664d03; font-size: .85rem;
        }

        @media (max-width: 768px) {
            #sidebar { transform: translateX(-100%); }
            #sidebar.show { transform: translateX(0); }
            #main-content { margin-left: 0; }
        }
    </style>

    @stack('styles')
</head>
<body>

{{-- ── Sidebar ─────────────────────────────────────────────────────────── --}}
<nav id="sidebar">
    <div class="sidebar-brand">
        <i class="bi bi-building me-2"></i>
        Head Office<br><small class="fw-normal opacity-75">Attendance System</small>
    </div>

    <ul class="nav flex-column mt-2 pb-4">

        {{-- Dashboard --}}
        @can('view_dashboard')
        <li class="nav-item">
            <a href="{{ route('dashboard') }}"
               class="nav-link {{ request()->routeIs('dashboard') ? 'active' : '' }}">
                <i class="bi bi-speedometer2"></i> Dashboard
            </a>
        </li>
        @endcan

        {{-- Organisation --}}
        <li><div class="nav-section">Organisation</div></li>
        @can('view_employees')
        <li class="nav-item">
            <a href="{{ route('employees.index') }}"
               class="nav-link {{ request()->routeIs('employees.*') ? 'active' : '' }}">
                <i class="bi bi-people"></i> Employees
            </a>
        </li>
        @endcan

        {{-- Attendance --}}
        <li><div class="nav-section">Attendance</div></li>
        @can('view_attendance')
        <li class="nav-item">
            <a href="{{ route('attendance.index') }}"
               class="nav-link {{ request()->routeIs('attendance.*') ? 'active' : '' }}">
                <i class="bi bi-clock-history"></i> Attendance Records
            </a>
        </li>
        @endcan

        {{-- Devices --}}
        <li><div class="nav-section">Devices</div></li>
        @can('view_devices')
        <li class="nav-item">
            <a href="{{ route('devices.index') }}"
               class="nav-link {{ request()->routeIs('devices.*') ? 'active' : '' }}">
                <i class="bi bi-cpu"></i> Devices
            </a>
        </li>
        @endcan
        @can('view_sync')
        <li class="nav-item">
            <a href="{{ route('sync.index') }}"
               class="nav-link {{ request()->routeIs('sync.*') ? 'active' : '' }}">
                <i class="bi bi-arrow-repeat"></i> Synchronisation
            </a>
        </li>
        @endcan

        {{-- Administration --}}
        <li><div class="nav-section">Administration</div></li>
        <li class="nav-item">
            <a href="#" class="nav-link text-muted" style="cursor:default" title="Coming in a later phase">
                <i class="bi bi-people-fill"></i> Users
            </a>
        </li>
        <li class="nav-item">
            <a href="#" class="nav-link text-muted" style="cursor:default" title="Coming in a later phase">
                <i class="bi bi-gear"></i> Settings
            </a>
        </li>

    </ul>
</nav>

{{-- ── Main content ────────────────────────────────────────────────────── --}}
<div id="main-content">

    {{-- Topbar --}}
    <header id="topbar">
        <button class="btn btn-sm btn-light d-md-none" id="sidebar-toggle">
            <i class="bi bi-list fs-5"></i>
        </button>
        <span class="fw-semibold text-secondary d-none d-md-block">@yield('title', 'Dashboard')</span>
        <div class="d-flex align-items-center gap-3">
            <span class="text-muted small">{{ Auth::user()->name }}</span>
            <form method="POST" action="{{ route('logout') }}" class="m-0">
                @csrf
                <button type="submit" class="btn btn-sm btn-outline-secondary">
                    <i class="bi bi-box-arrow-right"></i> Logout
                </button>
            </form>
        </div>
    </header>

    {{-- Flash messages --}}
    <div class="px-4 pt-3">
        @if(session('success'))
            <div class="alert alert-success alert-dismissible fade show py-2" role="alert">
                <i class="bi bi-check-circle-fill me-1"></i>{{ session('success') }}
                <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
            </div>
        @endif
        @if(session('error'))
            <div class="alert alert-danger alert-dismissible fade show py-2" role="alert">
                <i class="bi bi-exclamation-triangle-fill me-1"></i>{{ session('error') }}
                <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
            </div>
        @endif
    </div>

    {{-- Page content --}}
    <main class="page-content">
        @yield('content')
    </main>

    <footer class="text-center text-muted py-3" style="font-size:.75rem; border-top:1px solid #dee2e6">
        {{ config('app.name') }} &mdash; Phase 4 &mdash; {{ now()->format('Y') }}
    </footer>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
    // Mobile sidebar toggle
    document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('show');
    });
</script>
@stack('scripts')
</body>
</html>
