<?php

declare(strict_types=1);

namespace App\Providers;

use App\Models\User;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        // Register Gates for each permission slug so @can directives work
        $permissions = [
            'view_dashboard', 'manage_users', 'view_users', 'manage_roles',
            'view_branches', 'manage_branches', 'view_departments', 'manage_departments',
            'view_employees', 'manage_employees',
            'view_devices', 'manage_devices',
            'view_sync', 'run_sync',
            'view_attendance',
            'manage_settings', 'view_audit_logs',
        ];

        foreach ($permissions as $permission) {
            Gate::define($permission, function (User $user) use ($permission): bool {
                return $user->hasPermission($permission);
            });
        }
    }
}
