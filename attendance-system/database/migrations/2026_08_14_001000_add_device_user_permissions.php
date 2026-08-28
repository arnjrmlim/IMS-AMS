<?php

use App\Models\Permission;
use App\Models\Role;
use Illuminate\Database\Migrations\Migration;

/**
 * Adds view_device_users and manage_device_users permissions and assigns
 * them to the appropriate roles.
 *
 * Administrator — both (already gets all permissions via seeder sync)
 * HR            — both
 * Supervisor    — view only
 * Employee      — neither
 *
 * Safe to run on a live database. Uses firstOrCreate so re-running is harmless.
 */
return new class extends Migration
{
    public function up(): void
    {
        $view = Permission::firstOrCreate(
            ['slug' => 'view_device_users'],
            [
                'name'        => 'View Device Users',
                'group'       => 'devices',
                'description' => 'View Device Users',
            ]
        );

        $manage = Permission::firstOrCreate(
            ['slug' => 'manage_device_users'],
            [
                'name'        => 'Manage Device Users',
                'group'       => 'devices',
                'description' => 'Manage Device Users',
            ]
        );

        // Administrator gets everything
        $admin = Role::where('slug', 'administrator')->first();
        $admin?->permissions()->syncWithoutDetaching([$view->id, $manage->id]);

        // HR gets view + manage
        $hr = Role::where('slug', 'hr')->first();
        $hr?->permissions()->syncWithoutDetaching([$view->id, $manage->id]);

        // Supervisor gets view only
        $supervisor = Role::where('slug', 'supervisor')->first();
        $supervisor?->permissions()->syncWithoutDetaching([$view->id]);
    }

    public function down(): void
    {
        $slugs = ['view_device_users', 'manage_device_users'];

        Permission::whereIn('slug', $slugs)->each(function (Permission $p): void {
            $p->roles()->detach();
            $p->delete();
        });
    }
};
