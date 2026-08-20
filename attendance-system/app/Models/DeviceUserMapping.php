<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Maps a SpeedFace device user (device_user_id string) to an Employee.
 * employee_id is nullable — unmapped users are retained, never discarded.
 */
class DeviceUserMapping extends Model
{
    protected $fillable = [
        'device_id', 'device_user_id', 'employee_id',
        'device_name', 'mapping_status',
    ];

    public function device(): BelongsTo
    {
        return $this->belongsTo(Device::class);
    }

    public function employee(): BelongsTo
    {
        return $this->belongsTo(Employee::class);
    }

    public function isMapped(): bool
    {
        return $this->mapping_status === 'mapped' && $this->employee_id !== null;
    }
}
