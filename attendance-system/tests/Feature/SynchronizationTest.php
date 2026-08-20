<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Device;
use App\Models\Role;
use App\Models\SyncRun;
use App\Models\User;
use App\Services\SpeedFaceApiService;
use Database\Seeders\RolesAndPermissionsSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class SynchronizationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesAndPermissionsSeeder::class);
    }

    private function adminUser(): User
    {
        $user = User::factory()->create(['username' => 'admin', 'is_active' => true]);
        $user->roles()->attach(Role::where('slug', 'administrator')->first());
        return $user;
    }

    private function syncUser(): User
    {
        $user = User::factory()->create(['username' => 'syncer', 'is_active' => true]);
        $user->roles()->attach(Role::where('slug', 'hr')->first());
        return $user;
    }

    // ── Sync page ──────────────────────────────────────────────────────────

    public function test_sync_page_loads_for_authorised_user(): void
    {
        Http::fake([
            '*/sync/status'  => Http::response(['success' => true, 'data' => []], 200),
            '*/sync/history' => Http::response(['success' => true, 'data' => []], 200),
        ]);

        $this->actingAs($this->adminUser())
             ->get('/sync')
             ->assertStatus(200)
             ->assertSee('Synchronisation');
    }

    public function test_sync_page_shows_offline_banner_when_api_down(): void
    {
        Http::fake(['*' => fn () => throw new \Illuminate\Http\Client\ConnectionException('down')]);

        $this->actingAs($this->adminUser())
             ->get('/sync')
             ->assertStatus(200)
             ->assertSee('Integration service is offline');
    }

    // ── Sync trigger ───────────────────────────────────────────────────────

    public function test_trigger_sync_returns_202_and_creates_sync_run(): void
    {
        Http::fake([
            '*/sync' => Http::response(['success' => true, 'data' => ['message' => 'Started.']], 202),
        ]);

        Device::factory()->create();

        $this->actingAs($this->adminUser())
             ->postJson('/sync/trigger')
             ->assertStatus(202)
             ->assertJson(['success' => true]);

        $this->assertDatabaseHas('sync_runs', ['status' => 'running', 'source' => 'manual']);
    }

    public function test_trigger_sync_returns_409_when_already_running(): void
    {
        Http::fake([
            '*/sync' => Http::response(
                ['detail' => ['code' => 'SYNC_IN_PROGRESS', 'message' => 'Running.']],
                409
            ),
        ]);

        $this->actingAs($this->adminUser())
             ->postJson('/sync/trigger')
             ->assertStatus(409)
             ->assertJson(['code' => 'SYNC_IN_PROGRESS']);
    }

    public function test_trigger_sync_returns_503_when_service_offline(): void
    {
        Http::fake(['*/sync' => fn () => throw new \Illuminate\Http\Client\ConnectionException('down')]);

        $this->actingAs($this->adminUser())
             ->postJson('/sync/trigger')
             ->assertStatus(503);
    }

    public function test_unauthenticated_user_cannot_trigger_sync(): void
    {
        // Unauthenticated POST to a protected route must redirect to login (302)
        $this->postJson('/sync/trigger')
             ->assertStatus(401);
    }

    // ── Sync status poll ───────────────────────────────────────────────────

    public function test_status_endpoint_returns_sync_data(): void
    {
        Http::fake([
            '*/sync/status' => Http::response([
                'success' => true,
                'data'    => ['sync_in_progress' => false, 'last_sync_status' => 'success'],
            ], 200),
        ]);

        $this->actingAs($this->adminUser())
             ->getJson('/sync/status')
             ->assertStatus(200)
             ->assertJson(['ok' => true]);
    }

    public function test_status_endpoint_returns_offline_flag(): void
    {
        Http::fake(['*/sync/status' => fn () => throw new \Illuminate\Http\Client\ConnectionException('down')]);

        $this->actingAs($this->adminUser())
             ->getJson('/sync/status')
             ->assertStatus(200)
             ->assertJson(['ok' => false]);
    }
}
