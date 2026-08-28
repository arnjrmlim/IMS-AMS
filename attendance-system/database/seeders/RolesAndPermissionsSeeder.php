<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\Permission;
use App\Models\Role;
use Illuminate\Database\Seeder;

/**
 * Seeds roles and permissions.
 * Safe to re-run — uses firstOrCreate.
 */
class RolesAndPermissionsSeeder extends Seeder
{
    public function run(): void
    {
        // ── Roles ──────────────────────────────────────────────────────────
        $roles = [
            ['name' => 'Administrator', 'slug' => 'administrator', 'description' => 'Full system access'],
            ['name' => 'HR',            'slug' => 'hr',            'description' => 'Human resources management'],
            ['name' => 'Supervisor',    'slug' => 'supervisor',    'description' => 'Team supervision and attendance monitoring'],
            ['name' => 'Employee',      'slug' => 'employee',      'description' => 'Basic self-service access'],
        ];

        $createdRoles = [];
        foreach ($roles as $data) {
            $createdRoles[$data['slug']] = Role::firstOrCreate(
                ['slug' => $data['slug']],
                $data
            );
        }

        // ── Permissions ────────────────────────────────────────────────────
        $permissions = [
            // Dashboard
            ['group' => 'dashboard',     'slug' => 'view_dashboard',        'name' => 'View Dashboard'],

            // Users
            ['group' => 'users',         'slug' => 'manage_users',          'name' => 'Manage Users'],
            ['group' => 'users',         'slug' => 'view_users',            'name' => 'View Users'],

            // Roles
            ['group' => 'roles',         'slug' => 'manage_roles',          'name' => 'Manage Roles & Permissions'],

            // Organisation
            ['group' => 'organisation',  'slug' => 'view_branches',         'name' => 'View Branches'],
            ['group' => 'organisation',  'slug' => 'manage_branches',       'name' => 'Manage Branches'],
            ['group' => 'organisation',  'slug' => 'view_departments',      'name' => 'View Departments'],
            ['group' => 'organisation',  'slug' => 'manage_departments',    'name' => 'Manage Departments'],

            // Employees
            ['group' => 'employees',     'slug' => 'view_employees',        'name' => 'View Employees'],
            ['group' => 'employees',     'slug' => 'manage_employees',      'name' => 'Manage Employees'],

            // Devices
            ['group' => 'devices',       'slug' => 'view_devices',          'name' => 'View Devices'],
            ['group' => 'devices',       'slug' => 'manage_devices',        'name' => 'Manage Devices'],

            // Device Users
            ['group' => 'devices',       'slug' => 'view_device_users',     'name' => 'View Device Users'],
            ['group' => 'devices',       'slug' => 'manage_device_users',   'name' => 'Manage Device Users'],

            // Sync
            ['group' => 'sync',          'slug' => 'view_sync',             'name' => 'View Sync Status'],
            ['group' => 'sync',          'slug' => 'run_sync',              'name' => 'Trigger Synchronisation'],

            // Attendance
            ['group' => 'attendance',    'slug' => 'view_attendance',       'name' => 'View Attendance Records'],

            // Settings
            ['group' => 'settings',      'slug' => 'manage_settings',       'name' => 'Manage System Settings'],

            // Audit
            ['group' => 'audit',         'slug' => 'view_audit_logs',       'name' => 'View Audit Logs'],
        ];

        $createdPermissions = [];
        foreach ($permissions as $data) {
            $createdPermissions[$data['slug']] = Permission::firstOrCreate(
                ['slug' => $data['slug']],
                array_merge($data, ['description' => $data['name']])
            );
        }

        // ── Role → Permission assignments ──────────────────────────────────

        // Administrator gets everything
        $createdRoles['administrator']->permissions()->syncWithoutDetaching(
            collect($createdPermissions)->pluck('id')->toArray()
        );

        // HR
        $hrPermissions = [
            'view_dashboard', 'view_employees', 'manage_employees',
            'view_branches', 'view_departments',
            'view_attendance', 'view_sync', 'run_sync',
            'view_devices', 'view_device_users', 'manage_device_users',
        ];
        $createdRoles['hr']->permissions()->syncWithoutDetaching(
            collect($hrPermissions)->map(fn ($s) => $createdPermissions[$s]->id)->toArray()
        );

        // Supervisor
        $supervisorPermissions = [
            'view_dashboard', 'view_employees',
            'view_attendance', 'view_sync', 'view_devices',
            'view_device_users',
        ];
        $createdRoles['supervisor']->permissions()->syncWithoutDetaching(
            collect($supervisorPermissions)->map(fn ($s) => $createdPermissions[$s]->id)->toArray()
        );

        // Employee — minimal
        $createdRoles['employee']->permissions()->syncWithoutDetaching(
            [$createdPermissions['view_dashboard']->id]
        );
    }
}
