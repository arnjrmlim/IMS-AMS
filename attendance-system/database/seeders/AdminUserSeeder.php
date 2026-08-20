<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\Role;
use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

/**
 * Creates the initial administrator account.
 *
 * Credentials come from .env:
 *   INITIAL_ADMIN_USERNAME
 *   INITIAL_ADMIN_PASSWORD
 *   INITIAL_ADMIN_NAME
 *   INITIAL_ADMIN_EMAIL
 *
 * Safe to re-run — uses firstOrCreate on username.
 * Change the password after first login in production.
 */
class AdminUserSeeder extends Seeder
{
    public function run(): void
    {
        $username = env('INITIAL_ADMIN_USERNAME', 'admin');
        $password = env('INITIAL_ADMIN_PASSWORD', 'Admin@1234');
        $name     = env('INITIAL_ADMIN_NAME',     'System Administrator');
        $email    = env('INITIAL_ADMIN_EMAIL',    'admin@headoffice.local');

        $user = User::firstOrCreate(
            ['username' => $username],
            [
                'name'      => $name,
                'email'     => $email,
                'password'  => Hash::make($password),
                'is_active' => true,
            ]
        );

        $adminRole = Role::where('slug', 'administrator')->first();
        if ($adminRole && ! $user->roles()->where('slug', 'administrator')->exists()) {
            $user->roles()->attach($adminRole);
        }

        $this->command->info("Administrator ready — username: {$username}");
        $this->command->warn("Change the password after first login!");
    }
}
