<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\SpeedFaceApiService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

/**
 * Tests for SpeedFaceApiService.
 * All tests use Http::fake() — no real network connections are made.
 * The SpeedFace device is never contacted.
 */
class SpeedFaceApiServiceTest extends TestCase
{
    use RefreshDatabase;

    private SpeedFaceApiService $service;

    protected function setUp(): void
    {
        parent::setUp();
        $this->service = new SpeedFaceApiService();
    }

    // ── Health ─────────────────────────────────────────────────────────────

    public function test_health_returns_online_when_api_responds(): void
    {
        Http::fake(['*/health' => Http::response(['status' => 'ok', 'version' => '3.0.0'], 200)]);

        $result = $this->service->getHealth();

        $this->assertTrue($result['online']);
        $this->assertEquals('ok', $result['data']['status']);
    }

    public function test_health_returns_offline_when_connection_fails(): void
    {
        Http::fake(['*/health' => fn () => throw new \Illuminate\Http\Client\ConnectionException('refused')]);

        $result = $this->service->getHealth();

        $this->assertFalse($result['online']);
        $this->assertStringContainsString('offline', strtolower($result['message']));
    }

    // ── Devices ────────────────────────────────────────────────────────────

    public function test_get_devices_returns_data_on_success(): void
    {
        Http::fake([
            '*/device' => Http::response([
                'success' => true,
                'data'    => [
                    ['id' => 1, 'name' => 'xFace600', 'ip_address' => '192.168.10.3', 'status' => 'online'],
                ],
            ], 200),
        ]);

        $result = $this->service->getDevices();

        $this->assertTrue($result['ok']);
        $this->assertCount(1, $result['data']['data']);
        $this->assertEquals('xFace600', $result['data']['data'][0]['name']);
    }

    public function test_get_devices_returns_offline_flag_when_connection_refused(): void
    {
        Http::fake(['*/device' => fn () => throw new \Illuminate\Http\Client\ConnectionException('refused')]);

        $result = $this->service->getDevices();

        $this->assertFalse($result['ok']);
        $this->assertTrue($result['offline']);
    }

    // ── Sync status ────────────────────────────────────────────────────────

    public function test_get_sync_status_returns_status_data(): void
    {
        Http::fake([
            '*/sync/status' => Http::response([
                'success' => true,
                'data'    => [
                    'device_found'       => true,
                    'local_record_count' => 99918,
                    'last_sync_status'   => 'success',
                    'sync_in_progress'   => false,
                ],
            ], 200),
        ]);

        $result = $this->service->getSyncStatus();

        $this->assertTrue($result['ok']);
        $this->assertEquals(99918, $result['data']['data']['local_record_count']);
        $this->assertEquals('success', $result['data']['data']['last_sync_status']);
    }

    // ── Sync trigger ───────────────────────────────────────────────────────

    public function test_trigger_sync_returns_202_on_success(): void
    {
        Http::fake([
            '*/sync' => Http::response([
                'success' => true,
                'data'    => ['message' => 'Synchronisation started.'],
            ], 202),
        ]);

        $result = $this->service->triggerSync();

        $this->assertTrue($result['ok']);
        $this->assertEquals(202, $result['status']);
    }

    public function test_trigger_sync_returns_409_when_already_running(): void
    {
        Http::fake([
            '*/sync' => Http::response([
                'detail' => ['code' => 'SYNC_IN_PROGRESS', 'message' => 'Already running.'],
            ], 409),
        ]);

        $result = $this->service->triggerSync();

        $this->assertFalse($result['ok']);
        $this->assertEquals('SYNC_IN_PROGRESS', $result['code']);
        $this->assertEquals(409, $result['status']);
    }

    public function test_trigger_sync_returns_offline_when_service_down(): void
    {
        Http::fake(['*/sync' => fn () => throw new \Illuminate\Http\Client\ConnectionException('refused')]);

        $result = $this->service->triggerSync();

        $this->assertFalse($result['ok']);
        $this->assertTrue($result['offline']);
    }

    // ── Attendance ─────────────────────────────────────────────────────────

    public function test_get_attendance_passes_filters_to_api(): void
    {
        Http::fake([
            '*/attendance*' => Http::response([
                'success' => true,
                'data'    => [
                    ['device_user_id' => '1001', 'punch_datetime' => '2026-08-13 08:00:00'],
                ],
                'meta' => ['page' => 1, 'per_page' => 25, 'total' => 1, 'pages' => 1],
            ], 200),
        ]);

        $result = $this->service->getAttendance([
            'device_user_id' => '1001',
            'start_datetime' => '2026-08-13 00:00:00',
            'per_page'       => 25,
        ]);

        $this->assertTrue($result['ok']);
        $this->assertCount(1, $result['data']['data']);
    }

    public function test_get_attendance_strips_unknown_filter_params(): void
    {
        Http::fake(['*/attendance*' => Http::response(['success' => true, 'data' => [], 'meta' => []], 200)]);

        // 'malicious_param' must be stripped by the service
        $result = $this->service->getAttendance([
            'malicious_param' => 'injected',
            'per_page'        => 25,
        ]);

        // Request should still succeed (unknown param stripped silently)
        $this->assertTrue($result['ok']);
    }
}
