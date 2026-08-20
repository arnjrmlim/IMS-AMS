<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Role;
use App\Models\User;
use Database\Seeders\RolesAndPermissionsSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class AuthenticationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesAndPermissionsSeeder::class);
    }

    private function makeAdmin(string $username = 'admin', string $password = 'Admin@1234'): User
    {
        $user = User::factory()->create([
            'username'  => $username,
            'password'  => bcrypt($password),
            'is_active' => true,
        ]);
        $role = Role::where('slug', 'administrator')->first();
        if ($role) {
            $user->roles()->attach($role->id);
        }
        return $user;
    }

    // ── Login ──────────────────────────────────────────────────────────────

    public function test_login_page_is_accessible(): void
    {
        $this->get('/login')->assertStatus(200)->assertSee('Sign In');
    }

    public function test_valid_credentials_redirect_to_dashboard(): void
    {
        $user = $this->makeAdmin();
        $this->post('/login', ['username' => 'admin', 'password' => 'Admin@1234'])
             ->assertRedirect('/dashboard');
        $this->assertAuthenticatedAs($user);
    }

    public function test_invalid_password_returns_error(): void
    {
        $this->makeAdmin();
        $this->post('/login', ['username' => 'admin', 'password' => 'WrongPassword'])
             ->assertRedirect('/login')
             ->assertSessionHasErrors('username');
        $this->assertGuest();
    }

    public function test_unknown_username_returns_error(): void
    {
        $this->post('/login', ['username' => 'nobody', 'password' => 'anything'])
             ->assertRedirect('/login')
             ->assertSessionHasErrors('username');
    }

    public function test_missing_username_fails_validation(): void
    {
        $this->post('/login', ['username' => '', 'password' => 'Admin@1234'])
             ->assertSessionHasErrors('username');
    }

    public function test_missing_password_fails_validation(): void
    {
        $this->post('/login', ['username' => 'admin', 'password' => ''])
             ->assertSessionHasErrors('password');
    }

    // ── Logout ─────────────────────────────────────────────────────────────

    public function test_authenticated_user_can_logout(): void
    {
        $user = $this->makeAdmin();
        $this->actingAs($user)
             ->post('/logout')
             ->assertRedirect('/login');
        $this->assertGuest();
    }

    // ── Auth middleware ────────────────────────────────────────────────────

    public function test_unauthenticated_user_redirected_from_dashboard(): void
    {
        $this->get('/dashboard')->assertRedirect('/login');
    }

    public function test_unauthenticated_user_redirected_from_attendance(): void
    {
        $this->get('/attendance')->assertRedirect('/login');
    }

    public function test_unauthenticated_user_redirected_from_sync(): void
    {
        $this->get('/sync')->assertRedirect('/login');
    }

    public function test_unauthenticated_user_redirected_from_devices(): void
    {
        $this->get('/devices')->assertRedirect('/login');
    }

    // ── Inactive account ───────────────────────────────────────────────────

    public function test_inactive_user_cannot_login(): void
    {
        User::factory()->create([
            'username'  => 'inactive',
            'password'  => bcrypt('Admin@1234'),
            'is_active' => false,
        ]);

        // Inactive users are not blocked at login itself but at the active middleware.
        // Log them in then make a request to trigger the middleware.
        $this->post('/login', ['username' => 'inactive', 'password' => 'Admin@1234']);

        // Active middleware should log them out when they hit a protected route
        $this->get('/dashboard')
             ->assertRedirect('/login');
    }

    // ── Authorization ──────────────────────────────────────────────────────

    public function test_admin_can_access_dashboard(): void
    {
        $this->actingAs($this->makeAdmin())
             ->get('/dashboard')
             ->assertStatus(200);
    }

    public function test_user_without_permission_gets_403(): void
    {
        // User with no roles = no permissions
        $user = User::factory()->create(['username' => 'noperms', 'is_active' => true]);
        $this->actingAs($user)
             ->get('/dashboard')
             ->assertStatus(403);
    }
}
