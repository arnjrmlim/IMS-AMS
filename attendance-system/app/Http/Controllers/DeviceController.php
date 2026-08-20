<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Device;
use App\Models\SyncRun;
use App\Services\AuditService;
use App\Services\SpeedFaceApiService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\View\View;

class DeviceController extends Controller
{
    public function __construct(private SpeedFaceApiService $api) {}

    public function index(): View
    {
        $apiResult = $this->api->getDevices();
        $apiOnline = $apiResult['ok'] ?? false;

        // Sync API device list into local devices table
        if ($apiOnline) {
            $this->syncDevicesFromApi($apiResult['data']['data'] ?? []);
        }

        $devices = Device::with('branch')->orderBy('name')->get();

        return view('devices.index', compact('devices', 'apiOnline'));
    }

    public function show(Device $device): View
    {
        $apiDevice = $this->api->getDevice($device->speedface_device_id ?? 1);
        $apiData   = ($apiDevice['ok'] ?? false) ? ($apiDevice['data']['data'] ?? []) : [];

        $syncHistory = SyncRun::where('device_id', $device->id)
            ->orderByDesc('id')
            ->limit(10)
            ->get();

        AuditService::log('view_device', "Viewed device: {$device->name}", 'devices');

        return view('devices.show', compact('device', 'apiData', 'syncHistory'));
    }

    public function refresh(Device $device): JsonResponse
    {
        $result = $this->api->getDevice($device->speedface_device_id ?? 1);

        if (! ($result['ok'] ?? false)) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Could not reach integration service.',
            ], 503);
        }

        $data = $result['data']['data'] ?? [];

        // Update local device record from API response
        $device->update([
            'name'             => $data['name']             ?? $device->name,
            'firmware_version' => $data['firmware_version'] ?? $device->firmware_version,
            'platform'         => $data['platform']         ?? $device->platform,
            'user_count'       => $data['user_count']       ?? $device->user_count,
            'attendance_count' => $data['attendance_count'] ?? $device->attendance_count,
            'last_connected_at'=> $data['last_connected_at'] ? now() : $device->last_connected_at,
            'last_sync_at'     => $data['last_sync_at']     ?? $device->last_sync_at,
            'status'           => 'online',
        ]);

        return response()->json(['success' => true, 'device' => $device->fresh()]);
    }

    // ── Private helpers ────────────────────────────────────────────────────

    private function syncDevicesFromApi(array $apiDevices): void
    {
        foreach ($apiDevices as $d) {
            Device::updateOrCreate(
                ['speedface_device_id' => $d['id']],
                [
                    'name'             => $d['name']             ?? 'SpeedFace Device',
                    'model'            => $d['model']            ?? null,
                    'serial_number'    => $d['serial_number']    ?? null,
                    'ip_address'       => $d['ip_address']       ?? null,
                    'port'             => $d['port']             ?? 4370,
                    'firmware_version' => $d['firmware_version'] ?? null,
                    'platform'         => $d['platform']         ?? null,
                    'user_count'       => $d['user_count']       ?? null,
                    'attendance_count' => $d['attendance_count'] ?? null,
                    'last_sync_at'     => $d['last_sync_at']     ?? null,
                    'status'           => 'online',
                ]
            );
        }
    }
}
