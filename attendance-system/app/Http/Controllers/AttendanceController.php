<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Device;
use App\Models\Employee;
use App\Services\SpeedFaceApiService;
use Illuminate\Http\Request;
use Illuminate\View\View;

class AttendanceController extends Controller
{
    public function __construct(private SpeedFaceApiService $api) {}

    /**
     * Display paginated attendance records from the Python API.
     * Applies optional filters: device_id, device_user_id, date range.
     * No business calculations (late, overtime, absent) — Phase 6.
     */
    public function index(Request $request): View
    {
        $validated = $request->validate([
            'device_id'      => ['nullable', 'integer'],
            'device_user_id' => ['nullable', 'string', 'max:50'],
            'date_from'      => ['nullable', 'date_format:Y-m-d'],
            'date_to'        => ['nullable', 'date_format:Y-m-d'],
            'page'           => ['nullable', 'integer', 'min:1'],
            'per_page'       => ['nullable', 'integer', 'in:25,50,100'],
        ]);

        $perPage = (int) ($validated['per_page'] ?? 25);
        $page    = (int) ($validated['page']     ?? 1);

        $filters = ['page' => $page, 'per_page' => $perPage];

        if (! empty($validated['device_id'])) {
            $filters['device_id'] = $validated['device_id'];
        }
        if (! empty($validated['device_user_id'])) {
            $filters['device_user_id'] = $validated['device_user_id'];
        }
        if (! empty($validated['date_from'])) {
            $filters['start_datetime'] = $validated['date_from'].' 00:00:00';
        }
        if (! empty($validated['date_to'])) {
            $filters['end_datetime'] = $validated['date_to'].' 23:59:59';
        }

        $result  = $this->api->getAttendance($filters);
        $apiOnline = $result['ok'] ?? false;

        $records  = $apiOnline ? ($result['data']['data'] ?? []) : [];
        $meta     = $apiOnline ? ($result['data']['meta'] ?? []) : [];
        $errorMsg = $apiOnline ? null : ($result['message'] ?? 'Integration service is unavailable.');

        $devices   = Device::orderBy('name')->get();

        return view('attendance.index', compact(
            'records', 'meta', 'filters', 'devices',
            'apiOnline', 'errorMsg', 'perPage', 'page'
        ));
    }
}
