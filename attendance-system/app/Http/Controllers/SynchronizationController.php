<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Device;
use App\Models\SyncRun;
use App\Services\AuditService;
use App\Services\SpeedFaceApiService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\View\View;

class SynchronizationController extends Controller
{
    public function __construct(private SpeedFaceApiService $api) {}

    public function index(): View
    {
        $statusResult  = $this->api->getSyncStatus();
        $historyResult = $this->api->getSyncHistory(20);

        $syncStatus  = ($statusResult['ok']  ?? false) ? ($statusResult['data']['data']   ?? []) : null;
        $syncHistory = ($historyResult['ok'] ?? false) ? ($historyResult['data']['data']  ?? []) : [];
        $apiOnline   = $statusResult['ok'] ?? false;
        $offlineMsg  = $apiOnline ? null : ($statusResult['message'] ?? 'Integration service is unavailable.');

        // Close out any stuck 'running' runs if the Python side shows no sync in progress.
        // This handles the case where the user navigated away before the JS poll finished.
        if ($apiOnline && ! ($syncStatus['sync_in_progress'] ?? false)) {
            $this->closeStuckRuns($syncStatus ?? []);
        }

        // Local sync runs
        $localRuns = SyncRun::with(['device', 'triggeredBy'])
            ->orderByDesc('id')
            ->paginate(15);

        return view('sync.index', compact(
            'syncStatus', 'syncHistory', 'apiOnline', 'offlineMsg', 'localRuns'
        ));
    }

    /**
     * Trigger a read-only synchronisation via POST /api/sync.
     * Laravel → Python API → Python reads SpeedFace (READ ONLY)
     * Never communicates directly with the device.
     */
    public function trigger(Request $request): JsonResponse
    {
        $result = $this->api->triggerSync();

        if (! ($result['ok'] ?? false)) {
            $code = $result['code'] ?? 'API_ERROR';

            if ($code === 'SYNC_IN_PROGRESS') {
                return response()->json([
                    'success' => false,
                    'message' => 'A synchronisation is already in progress. Please wait.',
                    'code'    => 'SYNC_IN_PROGRESS',
                ], 409);
            }

            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Could not trigger synchronisation.',
            ], $result['offline'] ?? false ? 503 : 422);
        }

        // Record this trigger in local sync_runs
        $device = Device::first();
        $run = SyncRun::create([
            'device_id'    => $device?->id,
            'triggered_by' => Auth::id(),
            'status'       => 'running',
            'started_at'   => now(),
            'source'       => 'manual',
        ]);

        AuditService::log('sync_triggered', 'Manual synchronisation triggered via UI.', 'sync');

        return response()->json([
            'success' => true,
            'message' => 'Synchronisation started.',
            'run_id'  => $run->id,
        ], 202);
    }

    /**
     * Poll sync status — called by JS after triggering a sync.
     * Accepts an optional run_id query param so it can close out the
     * local SyncRun record once the Python sync completes.
     */
    public function status(Request $request): JsonResponse
    {
        $result = $this->api->getSyncStatus();

        if (! ($result['ok'] ?? false)) {
            return response()->json([
                'ok'      => false,
                'offline' => $result['offline'] ?? false,
                'message' => $result['message'] ?? 'Integration service unavailable.',
            ]);
        }

        $data       = $result['data']['data'] ?? [];
        $inProgress = $data['sync_in_progress'] ?? false;

        // When the Python sync has finished and we know the local run that
        // triggered it, update that SyncRun record with the real results.
        $runId = (int) $request->query('run_id', 0);
        if ($runId > 0 && ! $inProgress) {
            $run = SyncRun::find($runId);
            if ($run && $run->status === 'running') {
                $this->finaliseRun($run, $data);
            }
        }

        return response()->json([
            'ok'   => true,
            'data' => $data,
        ]);
    }

    // ── Private helpers ─────────────────────────────────────────────────────

    /**
     * Write the final status/counts onto a SyncRun record.
     * Uses UTC for both timestamps to avoid timezone-offset duration bugs.
     */
    private function finaliseRun(SyncRun $run, array $data): void
    {
        $lastRun     = $data['last_run'] ?? [];
        $status      = $data['last_sync_status'] ?? 'failed';
        $completedAt = now()->utc();

        // started_at is cast to Carbon — convert to UTC before diffing
        $startedAt   = $run->started_at?->utc();
        $durationSec = $startedAt ? max(0, $completedAt->diffInSeconds($startedAt)) : null;

        $run->update([
            'status'           => in_array($status, ['success', 'partial', 'failed']) ? $status : 'failed',
            'completed_at'     => $completedAt,
            'duration_seconds' => $durationSec,
            'records_read'     => $lastRun['records_read']     ?? 0,
            'records_inserted' => $lastRun['records_inserted'] ?? 0,
            'records_skipped'  => $lastRun['records_skipped']  ?? 0,
            'records_failed'   => $lastRun['records_failed']   ?? 0,
        ]);
    }

    /**
     * Close any runs that are stuck in 'running' state when the Python side
     * reports no sync is in progress. This handles the case where the user
     * navigated away before the JS poll had a chance to finalise the run.
     */
    private function closeStuckRuns(array $syncStatus): void
    {
        $stuckRuns = SyncRun::where('status', 'running')
            ->where('started_at', '<', now()->subMinutes(2)) // only close runs older than 2 min
            ->get();

        foreach ($stuckRuns as $run) {
            $this->finaliseRun($run, $syncStatus);
        }
    }
}
