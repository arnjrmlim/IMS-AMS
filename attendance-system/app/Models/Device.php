<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * Local representation of a SpeedFace device.
 * Source of truth is the Python Integration Service.
 * Laravel never communicates directly with port 4370.
 */
class Device extends Model
{
    use HasFactory;
    protected $fillable = [
        'branch_id', 'speedface_device_id', 'name', 'model',
        'serial_number', 'ip_address', 'port',
        'firmware_version', 'platform',
        'user_count', 'attendance_count',
        'status', 'last_connected_at', 'last_sync_at',
    ];

    protected function casts(): array
    {
        return [
            'last_connected_at' => 'datetime',
            'last_sync_at'      => 'datetime',
        ];
    }

    public function branch(): BelongsTo
    {
        return $this->belongsTo(Branch::class);
    }

    public function deviceUserMappings(): HasMany
    {
        return $this->hasMany(DeviceUserMapping::class);
    }

    public function attendanceRecords(): HasMany
    {
        return $this->hasMany(AttendanceRecord::class);
    }

    public function syncRuns(): HasMany
    {
        return $this->hasMany(SyncRun::class);
    }

    public function getIsOnlineAttribute(): bool
    {
        return $this->status === 'online';
    }

    public function getStatusBadgeAttribute(): string
    {
        return match($this->status) {
            'online'  => 'success',
            'offline' => 'danger',
            default   => 'secondary',
        };
    }
}
