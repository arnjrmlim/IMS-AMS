<?php

declare(strict_types=1);

use App\Http\Controllers\AttendanceController;
use App\Http\Controllers\Auth\LoginController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\DeviceController;
use App\Http\Controllers\DeviceUserMappingController;
use App\Http\Controllers\EmployeeController;
use App\Http\Controllers\SynchronizationController;
use Illuminate\Support\Facades\Route;

// ── Redirect root to dashboard ─────────────────────────────────────────────
Route::redirect('/', '/dashboard');

// ── Guest routes ───────────────────────────────────────────────────────────
Route::middleware('guest')->group(function (): void {
    Route::get('/login',  [LoginController::class, 'showLoginForm'])->name('login');
    Route::post('/login', [LoginController::class, 'login'])
        ->middleware('throttle:6,1')
        ->name('login.post');
});

// ── Authenticated routes ───────────────────────────────────────────────────
Route::middleware(['auth', 'active'])->group(function (): void {

    Route::post('/logout', [LoginController::class, 'logout'])->name('logout');

    // Dashboard
    Route::get('/dashboard', [DashboardController::class, 'index'])
        ->middleware('permission:view_dashboard')
        ->name('dashboard');

    // Devices
    Route::prefix('devices')->name('devices.')->group(function (): void {
        Route::get('/',             [DeviceController::class, 'index'])
            ->middleware('permission:view_devices')
            ->name('index');
        Route::get('/{device}',     [DeviceController::class, 'show'])
            ->middleware('permission:view_devices')
            ->name('show');
        Route::post('/{device}/refresh', [DeviceController::class, 'refresh'])
            ->middleware('permission:manage_devices')
            ->name('refresh');
    });

    // Synchronization
    Route::prefix('sync')->name('sync.')->group(function (): void {
        Route::get('/',        [SynchronizationController::class, 'index'])
            ->middleware('permission:view_sync')
            ->name('index');
        Route::post('/trigger', [SynchronizationController::class, 'trigger'])
            ->middleware('permission:run_sync')
            ->name('trigger');
        Route::get('/status',   [SynchronizationController::class, 'status'])
            ->middleware('permission:view_sync')
            ->name('status');
    });

    // Attendance
    Route::get('/attendance', [AttendanceController::class, 'index'])
        ->middleware('permission:view_attendance')
        ->name('attendance.index');

    // Employees (foundation)
    Route::prefix('employees')->name('employees.')->group(function (): void {
        Route::get('/',          [EmployeeController::class, 'index'])
            ->middleware('permission:view_employees')
            ->name('index');
        Route::get('/{employee}', [EmployeeController::class, 'show'])
            ->middleware('permission:view_employees')
            ->name('show');
    });

    // Device Users — Phase 4A (application-side only, SpeedFace is never modified)
    Route::prefix('device-users')->name('device-users.')->group(function (): void {
        Route::get('/', [DeviceUserMappingController::class, 'index'])
            ->middleware('permission:view_device_users')
            ->name('index');

        Route::get('/employee-search', [DeviceUserMappingController::class, 'employeeSearch'])
            ->middleware('permission:view_device_users')
            ->name('employee-search');

        Route::get('/{deviceUser}', [DeviceUserMappingController::class, 'show'])
            ->middleware('permission:view_device_users')
            ->name('show');

        Route::get('/{deviceUser}/edit', [DeviceUserMappingController::class, 'edit'])
            ->middleware('permission:manage_device_users')
            ->name('edit');

        Route::put('/{deviceUser}', [DeviceUserMappingController::class, 'update'])
            ->middleware('permission:manage_device_users')
            ->name('update');
    });
});
