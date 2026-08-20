<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AttendanceRecord;
use App\Models\Device;
use App\Models\Employee;
use App\Models\SyncRun;
use App\Services\SpeedFaceApiService;
use Illuminate\View\View;

class DashboardController extends Controller
{
    public function __construct(private SpeedFaceApiService $api) {}

    public function index(): View
    {
        // Python API health + sync status (never fails the page if offline)
        $health     = $this->api->getHealth();
        $syncStatus = $health['online'] ? $this->api->getSyncStatus() : ['ok' => false];

        $syncData   = ($syncStatus['ok'] ?? false)
            ? ($syncStatus['data']['data'] ?? [])
            : [];

        // Local DB counts
        $stats = [
            'devices'           => Device::count(),
            'online_devices'    => Device::where('status', 'online')->count(),
            'employees'         => Employee::where('status', 'active')->count(),
            'attendance_records'=> AttendanceRecord::count(),
        ];

        // Last sync run from local DB
        $lastSync = SyncRun::with('device')
            ->orderByDesc('id')
            ->first();

        return view('dashboard.index', compact(
            'health', 'syncData', 'stats', 'lastSync'
        ));
    }
}
