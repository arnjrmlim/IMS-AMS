<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SyncRun extends Model
{
    protected $fillable = [
        'device_id', 'triggered_by', 'status',
        'started_at', 'completed_at',
        'records_read', 'records_inserted', 'records_skipped',
        'records_failed', 'records_rejected',
        'duration_seconds', 'error_message', 'source',
    ];

    protected function casts(): array
    {
        return [
            'started_at'       => 'datetime',
            'completed_at'     => 'datetime',
            'duration_seconds' => 'decimal:2',
        ];
    }

    public function device(): BelongsTo
    {
        return $this->belongsTo(Device::class);
    }

    public function triggeredBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'triggered_by');
    }

    public function getStatusBadgeAttribute(): string
    {
        return match($this->status) {
            'success' => 'success',
            'partial' => 'warning',
            'failed'  => 'danger',
            'running' => 'info',
            default   => 'secondary',
        };
    }

    public function getDurationFormattedAttribute(): string
    {
        if ($this->duration_seconds === null) {
            return '—';
        }
        $seconds = (float) $this->duration_seconds;
        if ($seconds < 60) {
            return round($seconds, 1).'s';
        }
        $m = (int) ($seconds / 60);
        $s = (int) ($seconds % 60);
        return "{$m}m {$s}s";
    }
}
