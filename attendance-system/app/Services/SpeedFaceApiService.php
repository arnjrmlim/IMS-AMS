<?php

declare(strict_types=1);

namespace App\Services;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * HTTP client for the Phase 3 Python Integration Service REST API.
 *
 * ARCHITECTURE:
 *   Browser → Laravel → SpeedFaceApiService → Python API → SQLite
 *
 * The API key is NEVER exposed to the browser or JavaScript.
 * All communication with the Python service happens server-side only.
 *
 * The SpeedFace device is READ-ONLY. This service only consumes already-
 * synchronized data. It never sends commands to the device.
 */
class SpeedFaceApiService
{
    private string $baseUrl;
    private string $apiKey;
    private int    $timeout;

    public function __construct()
    {
        $this->baseUrl = rtrim(config('services.speedface.url', 'http://127.0.0.1:8000/api'), '/');
        $this->apiKey  = config('services.speedface.key', '');
        $this->timeout = (int) config('services.speedface.timeout', 30);
    }

    // ── Private helpers ────────────────────────────────────────────────────

    private function client(): \Illuminate\Http\Client\PendingRequest
    {
        return Http::timeout($this->timeout)
            ->withToken($this->apiKey)
            ->acceptJson();
    }

    private function get(string $path, array $query = []): array
    {
        try {
            $response = $this->client()->get($this->baseUrl.$path, $query);

            if ($response->successful()) {
                return ['ok' => true, 'data' => $response->json()];
            }

            Log::warning('SpeedFace API non-2xx response', [
                'path'   => $path,
                'status' => $response->status(),
            ]);

            return [
                'ok'      => false,
                'status'  => $response->status(),
                'message' => $response->json('detail.message') ?? $response->json('message') ?? 'API error',
            ];
        } catch (ConnectionException $e) {
            Log::error('SpeedFace API connection failed', [
                'path'    => $path,
                'message' => $e->getMessage(),
            ]);
            return ['ok' => false, 'offline' => true, 'message' => 'Integration service is offline.'];
        } catch (\Throwable $e) {
            Log::error('SpeedFace API unexpected error', [
                'path'    => $path,
                'message' => $e->getMessage(),
            ]);
            return ['ok' => false, 'message' => 'Unexpected error contacting integration service.'];
        }
    }

    private function post(string $path, array $data = []): array
    {
        try {
            $response = $this->client()->post($this->baseUrl.$path, $data);

            if ($response->status() === 202 || $response->successful()) {
                return ['ok' => true, 'data' => $response->json(), 'status' => $response->status()];
            }

            $code = $response->json('detail.code') ?? 'API_ERROR';
            $msg  = $response->json('detail.message') ?? 'API error';

            return ['ok' => false, 'status' => $response->status(), 'code' => $code, 'message' => $msg];
        } catch (ConnectionException $e) {
            Log::error('SpeedFace API POST connection failed', ['path' => $path, 'message' => $e->getMessage()]);
            return ['ok' => false, 'offline' => true, 'message' => 'Integration service is offline.'];
        } catch (\Throwable $e) {
            Log::error('SpeedFace API POST unexpected error', ['path' => $path, 'message' => $e->getMessage()]);
            return ['ok' => false, 'message' => 'Unexpected error contacting integration service.'];
        }
    }

    // ── Public API methods ─────────────────────────────────────────────────

    /**
     * GET /api/health — no auth required.
     * Returns ['ok' => bool, 'online' => bool].
     */
    public function getHealth(): array
    {
        try {
            $response = Http::timeout(5)->get($this->baseUrl.'/health');
            return ['ok' => true, 'online' => $response->successful(), 'data' => $response->json()];
        } catch (\Throwable) {
            return ['ok' => false, 'online' => false, 'message' => 'Integration service is offline.'];
        }
    }

    /**
     * GET /api/device — list all registered devices.
     */
    public function getDevices(): array
    {
        return $this->get('/device');
    }

    /**
     * GET /api/device/{id} — single device detail.
     */
    public function getDevice(int $id): array
    {
        return $this->get("/device/{$id}");
    }

    /**
     * GET /api/sync/status — current synchronisation status.
     */
    public function getSyncStatus(): array
    {
        return $this->get('/sync/status');
    }

    /**
     * GET /api/sync/history — recent sync run history.
     */
    public function getSyncHistory(int $limit = 10): array
    {
        return $this->get('/sync/history', ['limit' => $limit]);
    }

    /**
     * POST /api/sync — trigger a read-only device synchronisation.
     * Returns 202 Accepted when started, 409 if already running.
     * DEVICE POLICY: This only triggers a READ from the SpeedFace. Never writes.
     */
    public function triggerSync(): array
    {
        return $this->post('/sync');
    }

    /**
     * GET /api/attendance — paginated attendance records with optional filters.
     */
    public function getAttendance(array $filters = []): array
    {
        $allowed = ['device_id', 'device_user_id', 'start_datetime', 'end_datetime', 'page', 'per_page'];
        return $this->get('/attendance', array_intersect_key($filters, array_flip($allowed)));
    }

    /**
     * GET /api/device-users — paginated device users.
     */
    public function getDeviceUsers(int $deviceId = null, int $page = 1, int $perPage = 100): array
    {
        $query = ['page' => $page, 'per_page' => $perPage];
        if ($deviceId !== null) {
            $query['device_id'] = $deviceId;
        }
        return $this->get('/device-users', $query);
    }
}
