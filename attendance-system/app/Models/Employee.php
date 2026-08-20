<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Employee extends Model
{
    protected $fillable = [
        'employee_number', 'first_name', 'middle_name', 'last_name', 'suffix',
        'branch_id', 'department_id', 'position',
        'employment_status', 'date_hired', 'email', 'contact_number', 'status',
    ];

    protected function casts(): array
    {
        return ['date_hired' => 'date'];
    }

    // ── Relationships ──────────────────────────────────────────────────────

    public function branch(): BelongsTo
    {
        return $this->belongsTo(Branch::class);
    }

    public function department(): BelongsTo
    {
        return $this->belongsTo(Department::class);
    }

    public function deviceMappings(): HasMany
    {
        return $this->hasMany(DeviceUserMapping::class);
    }

    public function attendanceRecords(): HasMany
    {
        return $this->hasMany(AttendanceRecord::class);
    }

    // ── Accessors ──────────────────────────────────────────────────────────

    public function getFullNameAttribute(): string
    {
        $parts = array_filter([
            $this->first_name,
            $this->middle_name ? mb_substr($this->middle_name, 0, 1).'.' : null,
            $this->last_name,
            $this->suffix,
        ]);
        return implode(' ', $parts);
    }
}
