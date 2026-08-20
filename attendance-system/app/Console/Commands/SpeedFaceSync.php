<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\SpeedFaceApiService;
use Illuminate\Console\Command;

/**
 * php artisan speedface:sync [--dry-run]
 *
 * Triggers a read-only attendance synchronisation via the Python API.
 *
 * Flow:
 *   Laravel Artisan
 *     → SpeedFaceApiService
 *     → Python REST API (POST /api/sync)
 *     → Python Sync Service
 *     → SpeedFace READ ONLY
 *
 * NEVER communicates directly with the SpeedFace device.
 * NEVER calls any ZKTeco protocol command from Laravel.
 */
class SpeedFaceSync extends Command
{
    protected $signature   = 'speedface:sync';
    protected $description = 'Trigger attendance synchronisation via the Python Integration Service';

    public function handle(SpeedFaceApiService $api): int
    {
        $this->info('Triggering synchronisation via Python Integration Service ...');
        $this->line('Flow: Laravel → Python API → SpeedFace (READ ONLY)');
        $this->newLine();

        $result = $api->triggerSync();

        if ($result['ok'] ?? false) {
            $status = $result['status'] ?? 202;
            if ($status === 202) {
                $this->info('✓ Synchronisation started (202 Accepted).');
                $this->line('  The Python service is now fetching attendance records.');
                $this->line('  Run: php artisan speedface:health  to check service status.');
                return Command::SUCCESS;
            }
            $this->info('✓ Response: '.$status);
            return Command::SUCCESS;
        }

        $code = $result['code'] ?? 'ERROR';

        if ($code === 'SYNC_IN_PROGRESS') {
            $this->warn('⚠ A synchronisation is already running. Wait for it to complete.');
            return Command::FAILURE;
        }

        if ($result['offline'] ?? false) {
            $this->error('✗ Integration service is OFFLINE.');
            $this->line('  Start it: cd speedface-integration && python run.py serve');
            return Command::FAILURE;
        }

        $this->error('✗ Sync trigger failed: '.($result['message'] ?? 'Unknown error'));
        return Command::FAILURE;
    }
}
