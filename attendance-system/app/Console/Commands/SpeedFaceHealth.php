<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\SpeedFaceApiService;
use Illuminate\Console\Command;

/**
 * php artisan speedface:health
 * Checks whether the Python Integration Service is reachable.
 * NEVER communicates directly with the SpeedFace device.
 */
class SpeedFaceHealth extends Command
{
    protected $signature   = 'speedface:health';
    protected $description = 'Check the health of the Python Integration Service API';

    public function handle(SpeedFaceApiService $api): int
    {
        $this->info('Checking Python Integration Service health ...');
        $result = $api->getHealth();

        if ($result['online'] ?? false) {
            $data = $result['data'] ?? [];
            $this->info('✓ Integration service is ONLINE');
            $this->line('  Status  : '.($data['status']  ?? 'ok'));
            $this->line('  Version : '.($data['version'] ?? '?'));
            $this->line('  Service : '.($data['service'] ?? '?'));
            return Command::SUCCESS;
        }

        $this->error('✗ Integration service is OFFLINE');
        $this->line('  '.$result['message'] ?? 'Could not connect.');
        $this->line('  Verify that the Python service is running:');
        $this->line('  cd speedface-integration && python run.py serve');
        return Command::FAILURE;
    }
}
