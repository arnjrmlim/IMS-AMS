<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AttendanceRecord;
use App\Models\Branch;
use App\Models\Department;
use App\Models\Device;
use App\Models\Employee;
use App\Models\Role;
use App\Models\User;
use Database\Seeders\RolesAndPermissionsSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class AttendanceTest extends TestCase
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

    // ── Attendance page ────────────────────────────────────────────────────

    public function test_attendance_page_loads_for_authorised_user(): void
    {
        Http::fake([
            '*/attendance*' => Http::response([
                'success' => true,
                'data'    => [],
                'meta'    => ['page' => 1, 'per_page' => 25, 'total' => 0, 'pages' => 0],
            ], 200),
        ]);

        $this->actingAs($this->adminUser())
             ->get('/attendance')
             ->assertStatus(200)
             ->assertSee('Attendance Records');
    }

    public function test_attendance_page_shows_offline_message_when_api_down(): void
    {
        Http::fake(['*' => fn () => throw new \Illuminate\Http\Client\ConnectionException('down')]);

        $this->actingAs($this->adminUser())
             ->get('/attendance')
             ->assertStatus(200)
             ->assertSee('Integration service is offline');
    }

    public function test_attendance_pagination_request_passes_per_page(): void
    {
        Http::fake([
            '*/attendance*' => Http::response([
                'success' => true,
                'data'    => [],
                'meta'    => ['page' => 1, 'per_page' => 50, 'total' => 0, 'pages' => 0],
            ], 200),
        ]);

        $this->actingAs($this->adminUser())
             ->get('/attendance?per_page=50')
             ->assertStatus(200);

        // Verify the API was called with per_page=50
        Http::assertSent(fn ($req) => str_contains($req->url(), 'per_page=50'));
    }

    public function test_attendance_filter_by_device_user_id(): void
    {
        Http::fake([
            '*/attendance*' => Http::response([
                'success' => true,
                'data'    => [
                    ['device_user_id' => '1001', 'punch_datetime' => '2026-08-13 08:00:00',
                     'punch_state' => 0, 'punch_state_label' => 'Check In',
                     'verification_type' => 10, 'verification_type_label' => 'Face'],
                ],
                'meta' => ['page' => 1, 'per_page' => 25, 'total' => 1, 'pages' => 1],
            ], 200),
        ]);

        $this->actingAs($this->adminUser())
             ->get('/attendance?device_user_id=1001')
             ->assertStatus(200)
             ->assertSee('1001');

        Http::assertSent(fn ($req) => str_contains($req->url(), 'device_user_id=1001'));
    }

    public function test_invalid_per_page_rejected(): void
    {
        $this->actingAs($this->adminUser())
             ->get('/attendance?per_page=9999')
             ->assertSessionHasErrors('per_page');
    }

    public function test_invalid_date_format_rejected(): void
    {
        $this->actingAs($this->adminUser())
             ->get('/attendance?date_from=not-a-date')
             ->assertSessionHasErrors('date_from');
    }

    // ── Duplicate protection (DB layer) ───────────────────────────────────

    public function test_duplicate_attendance_record_cannot_be_inserted(): void
    {
        $device = Device::factory()->create();

        $data = [
            'device_id'          => $device->id,
            'device_user_id'     => '1001',
            'punch_datetime'     => '2026-08-13 08:00:00',
            'punch_state'        => 0,
            'verification_type'  => 10,
        ];

        AttendanceRecord::create($data);

        $this->expectException(\Illuminate\Database\UniqueConstraintViolationException::class);
        AttendanceRecord::create($data);
    }

    public function test_same_user_different_datetime_is_allowed(): void
    {
        $device = Device::factory()->create();

        AttendanceRecord::create([
            'device_id' => $device->id, 'device_user_id' => '1001',
            'punch_datetime' => '2026-08-13 08:00:00', 'punch_state' => 0, 'verification_type' => 10,
        ]);
        AttendanceRecord::create([
            'device_id' => $device->id, 'device_user_id' => '1001',
            'punch_datetime' => '2026-08-13 17:00:00', 'punch_state' => 1, 'verification_type' => 10,
        ]);

        $this->assertEquals(2, AttendanceRecord::count());
    }

    // ── Unmapped users ─────────────────────────────────────────────────────

    public function test_attendance_record_without_employee_mapping_is_retained(): void
    {
        $device = Device::factory()->create();

        // Create record with no employee_id (unmapped)
        $record = AttendanceRecord::create([
            'device_id'         => $device->id,
            'device_user_id'    => '9999',  // no employee mapped
            'punch_datetime'    => '2026-08-13 08:00:00',
            'punch_state'       => 0,
            'verification_type' => 10,
            'employee_id'       => null,
        ]);

        $this->assertNull($record->employee_id);
        $this->assertDatabaseHas('attendance_records', [
            'device_user_id' => '9999',
            'employee_id'    => null,
        ]);
    }
}
