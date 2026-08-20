<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;

class User extends Authenticatable
{
    use HasFactory, Notifiable;

    protected $fillable = [
        'name',
        'username',
        'email',
        'password',
        'is_active',
        'last_login_at',
    ];

    protected $hidden = [
        'password',
        'remember_token',
    ];

    protected function casts(): array
    {
        return [
            'password'       => 'hashed',
            'is_active'      => 'boolean',
            'last_login_at'  => 'datetime',
        ];
    }

    // ── Relationships ──────────────────────────────────────────────────────

    public function roles(): BelongsToMany
    {
        return $this->belongsToMany(Role::class);
    }

    public function auditLogs(): HasMany
    {
        return $this->hasMany(AuditLog::class);
    }

    public function syncRuns(): HasMany
    {
        return $this->hasMany(SyncRun::class, 'triggered_by');
    }

    // ── Permission helpers ─────────────────────────────────────────────────

    public function hasRole(string $slug): bool
    {
        return $this->roles()->where('slug', $slug)->exists();
    }

    public function hasPermission(string $slug): bool
    {
        return $this->roles()
            ->whereHas('permissions', fn ($q) => $q->where('slug', $slug))
            ->exists();
    }

    public function isAdministrator(): bool
    {
        return $this->hasRole('administrator');
    }

    public function getFullNameAttribute(): string
    {
        return $this->name;
    }
}
