<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Local copy of a punch transaction synchronized from the SpeedFace device.
 *
 * Source: Python Integration Service → Phase 3 REST API → this table.
 * The Laravel app never reads directly from the device.
 *
 * No business calculations (late, overtime, absent) are stored here.
 */
class AttendanceRecord extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'device_id', 'device_user_id', 'employee_id',
        'punch_datetime', 'punch_state', 'punch_state_label',
        'verification_type', 'verification_type_label',
        'source_record_id', 'raw_data', 'synced_at',
    ];

    protected function casts(): array
    {
        return [
            'punch_datetime' => 'datetime',
            'synced_at'      => 'datetime',
        ];
    }

    // ── Relationships ──────────────────────────────────────────────────────

    public function device(): BelongsTo
    {
        return $this->belongsTo(Device::class);
    }

    public function employee(): BelongsTo
    {
        return $this->belongsTo(Employee::class);
    }

    // ── Scopes ─────────────────────────────────────────────────────────────

    public function scopeForDevice(Builder $query, int $deviceId): Builder
    {
        return $query->where('device_id', $deviceId);
    }

    public function scopeForDeviceUser(Builder $query, string $deviceUserId): Builder
    {
        return $query->where('device_user_id', $deviceUserId);
    }

    public function scopeBetweenDates(Builder $query, string $from, string $to): Builder
    {
        return $query->whereBetween('punch_datetime', [$from, $to]);
    }

    public function scopeUnmapped(Builder $query): Builder
    {
        return $query->whereNull('employee_id');
    }

    // ── Accessors ──────────────────────────────────────────────────────────

    public function getPunchStateNameAttribute(): string
    {
        return $this->punch_state_label ?? match($this->punch_state) {
            0 => 'Check In',
            1 => 'Check Out',
            2 => 'Break Out',
            3 => 'Break In',
            4 => 'Overtime In',
            5 => 'Overtime Out',
            default => 'State '.$this->punch_state,
        };
    }

    public function getVerificationNameAttribute(): string
    {
        return $this->verification_type_label ?? match(true) {
            $this->verification_type >= 10 && $this->verification_type < 15 => 'Face',
            $this->verification_type === 15 => 'Password',
            $this->verification_type >= 16 && $this->verification_type < 20 => 'Card',
            default => 'Fingerprint',
        };
    }
}
