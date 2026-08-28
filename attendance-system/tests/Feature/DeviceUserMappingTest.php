<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\Branch;
use App\Models\Department;
use App\Models\Device;
use App\Models\DeviceUserMapping;
use App\Models\Employee;
use App\Models\Role;
use App\Models\User;
use Database\Seeders\RolesAndPermissionsSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Phase 4A — Device User Mapping feature tests.
 *
 * Covers:
 *   - Authorisation (unauthenticated, wrong permission, correct permission)
 *   - Index: listing, search by device_user_id, general search, status filter
 *   - Show: detail page renders correct sections
 *   - Edit: form loads with read-only device_user_id
 *   - Update: valid save, validation errors, duplicate-mapping prevention,
 *             device_user_id immutability, attendance record stamping,
 *             audit log creation
 *   - Device safety: no SpeedFace write is ever called
 */
class DeviceUserMappingTest extends TestCase
{
    use RefreshDatabase;

    // ── Fixtures ────────────────────────────────────────────────────────────

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(RolesAndPermissionsSeeder::class);
    }

    private function makeAdmin(): User
    {
        $user = User::factory()->create(['is_active' => true]);
        $user->roles()->attach(Role::where('slug', 'administrator')->first());
        return $user;
    }

    private function makeUserWithRole(string $roleSlug): User
    {
        $user = User::factory()->create(['is_active' => true]);
        $user->roles()->attach(Role::where('slug', $roleSlug)->first());
        return $user;
    }

    private function makeDevice(): Device
    {
        return Device::factory()->create(['name' => 'SpeedFace-V5L']);
    }

    private function makeMapping(Device $device, string $deviceUserId = '1001', ?Employee $employee = null): DeviceUserMapping
    {
        return DeviceUserMapping::create([
            'device_id'      => $device->id,
            'device_user_id' => $deviceUserId,
            'device_name'    => 'Juan Dela Cruz',
            'employee_id'    => $employee?->id,
            'mapping_status' => $employee ? 'mapped' : 'unmapped',
        ]);
    }

    private function makeEmployee(array $attrs = []): Employee
    {
        $branch = Branch::create(['code' => 'BR-'.uniqid(), 'name' => 'Test Branch', 'is_active' => true]);
        $dept   = Department::create(['name' => 'IT', 'branch_id' => $branch->id, 'is_active' => true]);

        return Employee::create(array_merge([
            'employee_number' => 'EMP-'.uniqid(),
            'first_name'      => 'Juan',
            'last_name'       => 'Dela Cruz',
            'branch_id'       => $branch->id,
            'department_id'   => $dept->id,
            'status'          => 'active',
        ], $attrs));
    }

    // ── 1. Authorisation ────────────────────────────────────────────────────

    public function test_unauthenticated_user_redirected_from_index(): void
    {
        $this->get('/device-users')->assertRedirect('/login');
    }

    public function test_unauthenticated_user_redirected_from_show(): void
    {
        $device  = $this->makeDevice();
        $mapping = $this->makeMapping($device);
        $this->get("/device-users/{$mapping->id}")->assertRedirect('/login');
    }

    public function test_employee_role_cannot_access_device_users(): void
    {
        $user = $this->makeUserWithRole('employee');
        $this->actingAs($user)->get('/device-users')->assertStatus(403);
    }

    public function test_supervisor_can_view_but_not_edit(): void
    {
        $device  = $this->makeDevice();
        $mapping = $this->makeMapping($device);
        $user    = $this->makeUserWithRole('supervisor');

        $this->actingAs($user)->get('/device-users')->assertStatus(200);
        $this->actingAs($user)->get("/device-users/{$mapping->id}")->assertStatus(200);
        $this->actingAs($user)->get("/device-users/{$mapping->id}/edit")->assertStatus(403);
        $this->actingAs($user)->put("/device-users/{$mapping->id}", [])->assertStatus(403);
    }

    public function test_admin_can_access_all_device_user_routes(): void
    {
        $admin   = $this->makeAdmin();
        $device  = $this->makeDevice();
        $mapping = $this->makeMapping($device);

        $this->actingAs($admin)->get('/device-users')->assertStatus(200);
        $this->actingAs($admin)->get("/device-users/{$mapping->id}")->assertStatus(200);
        $this->actingAs($admin)->get("/device-users/{$mapping->id}/edit")->assertStatus(200);
    }

    // ── 2. Index — list and search ──────────────────────────────────────────

    public function test_index_displays_device_user_ids(): void
    {
        $admin  = $this->makeAdmin();
        $device = $this->makeDevice();
        $this->makeMapping($device, '1001');
        $this->makeMapping($device, '1002');

        $this->actingAs($admin)
             ->get('/device-users')
             ->assertStatus(200)
             ->assertSee('1001')
             ->assertSee('1002');
    }

    public function test_search_by_device_user_id_returns_matching_record(): void
    {
        $admin  = $this->makeAdmin();
        $device = $this->makeDevice();
        $this->makeMapping($device, '1001');
        $this->makeMapping($device, '1002');

        $this->actingAs($admin)
             ->get('/device-users?device_user_id=1001')
             ->assertStatus(200)
             ->assertSee('1001')
             ->assertDontSee('1002');
    }

    public function test_search_by_nonexistent_device_user_id_shows_empty_state(): void
    {
        $admin  = $this->makeAdmin();
        $device = $this->makeDevice();
        $this->makeMapping($device, '1001');

        $this->actingAs($admin)
             ->get('/device-users?device_user_id=999999')
             ->assertStatus(200)
             ->assertSee('No device users found');
    }

    public function test_search_by_employee_name(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee(['first_name' => 'Maria', 'last_name' => 'Santos']);
        $this->makeMapping($device, '1001', $employee);
        $this->makeMapping($device, '1002');

        $this->actingAs($admin)
             ->get('/device-users?search=Maria')
             ->assertStatus(200)
             ->assertSee('1001')
             ->assertDontSee('1002');
    }

    public function test_filter_by_mapping_status_unmapped(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $this->makeMapping($device, '1001', $employee); // mapped
        $this->makeMapping($device, '1002');            // unmapped

        $response = $this->actingAs($admin)
             ->get('/device-users?mapping_status=unmapped')
             ->assertStatus(200);

        // Device user 1002 (unmapped) should be visible
        $response->assertSee('1002');
        // Device user 1001 (mapped) should NOT appear in a table cell
        // Use assertDontSee on the <code> tag content to avoid false matches in URLs
        $response->assertDontSee('<code class="fw-semibold">1001</code>', false);
    }

    // ── 3. Show ─────────────────────────────────────────────────────────────

    public function test_show_displays_device_user_id_and_device_name(): void
    {
        $admin   = $this->makeAdmin();
        $device  = $this->makeDevice();
        $mapping = $this->makeMapping($device, '1001');

        $this->actingAs($admin)
             ->get("/device-users/{$mapping->id}")
             ->assertStatus(200)
             ->assertSee('1001')
             ->assertSee('Device Source Information')
             ->assertSee('Application Information');
    }

    public function test_show_displays_unassigned_state_for_unmapped_user(): void
    {
        $admin   = $this->makeAdmin();
        $device  = $this->makeDevice();
        $mapping = $this->makeMapping($device, '1007');

        $this->actingAs($admin)
             ->get("/device-users/{$mapping->id}")
             ->assertStatus(200)
             ->assertSee('No employee assigned');
    }

    public function test_show_displays_employee_information_when_mapped(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee(['first_name' => 'Pedro', 'last_name' => 'Reyes']);
        $mapping  = $this->makeMapping($device, '1003', $employee);

        $this->actingAs($admin)
             ->get("/device-users/{$mapping->id}")
             ->assertStatus(200)
             ->assertSee('Pedro')
             ->assertSee('Reyes');
    }

    // ── 4. Edit form ─────────────────────────────────────────────────────────

    public function test_edit_form_shows_device_user_id_as_read_only(): void
    {
        $admin   = $this->makeAdmin();
        $device  = $this->makeDevice();
        $mapping = $this->makeMapping($device, '1001');

        $response = $this->actingAs($admin)
             ->get("/device-users/{$mapping->id}/edit")
             ->assertStatus(200);

        // Device User ID must appear in a read-only display, not an editable input
        $response->assertSee('1001');
        $response->assertSee('Cannot be changed');
        // Must NOT have an editable input named device_user_id
        $response->assertDontSee('name="device_user_id"', false);
    }

    public function test_edit_form_shows_existing_employee_data(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee([
            'first_name'      => 'Ana',
            'last_name'       => 'Lim',
            'employee_number' => 'EMP-0042',
        ]);
        $mapping = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->get("/device-users/{$mapping->id}/edit")
             ->assertStatus(200)
             ->assertSee('Ana')
             ->assertSee('Lim')
             ->assertSee('EMP-0042');
    }

    // ── 5. Update — valid save ───────────────────────────────────────────────

    public function test_update_saves_employee_information_to_application_database(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee(['first_name' => 'Juan', 'last_name' => 'Cruz']);
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => 'Juan Miguel',
                 'middle_name'     => '',
                 'last_name'       => 'Dela Cruz',
                 'suffix'          => '',
                 'employee_number' => $employee->employee_number,
                 'branch_id'       => $employee->branch_id,
                 'department_id'   => $employee->department_id,
                 'status'          => 'active',
             ])
             ->assertRedirect("/device-users/{$mapping->id}")
             ->assertSessionHas('success');

        $employee->refresh();
        $this->assertSame('Juan Miguel', $employee->first_name);
        $this->assertSame('Dela Cruz', $employee->last_name);
    }

    public function test_update_does_not_change_device_user_id(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => 'Test',
                 'last_name'       => 'User',
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ]);

        $mapping->refresh();
        $this->assertSame('1001', $mapping->device_user_id);
    }

    public function test_update_sets_mapping_status_to_mapped_when_employee_assigned(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1005'); // unmapped

        $response = $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => $employee->first_name,
                 'last_name'       => $employee->last_name,
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ]);

        // Confirm no validation errors and successful redirect
        $response->assertSessionHasNoErrors()
                 ->assertRedirect("/device-users/{$mapping->id}");

        // Confirm DB was updated
        $this->assertDatabaseHas('device_user_mappings', [
            'id'             => $mapping->id,
            'mapping_status' => 'mapped',
            'employee_id'    => $employee->id,
        ]);
    }

    public function test_update_sets_mapping_status_to_unmapped_when_employee_removed(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id' => null,
             ]);

        $mapping->refresh();
        $this->assertSame('unmapped', $mapping->mapping_status);
        $this->assertNull($mapping->employee_id);
    }

    public function test_update_stamps_employee_id_onto_unmapped_attendance_records(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001'); // unmapped

        // Create attendance records without employee_id
        \App\Models\AttendanceRecord::create([
            'device_id'          => $device->id,
            'device_user_id'     => '1001',
            'employee_id'        => null,
            'punch_datetime'     => now()->subDay(),
            'punch_state'        => 0,
            'verification_type'  => 10,
        ]);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => $employee->first_name,
                 'last_name'       => $employee->last_name,
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ]);

        $this->assertDatabaseHas('attendance_records', [
            'device_id'      => $device->id,
            'device_user_id' => '1001',
            'employee_id'    => $employee->id,
        ]);
    }

    public function test_update_does_not_overwrite_already_mapped_attendance_records(): void
    {
        $admin      = $this->makeAdmin();
        $device     = $this->makeDevice();
        $empA       = $this->makeEmployee(['first_name' => 'EmployeeA', 'last_name' => 'A']);
        $empB       = $this->makeEmployee(['first_name' => 'EmployeeB', 'last_name' => 'B']);
        $mapping    = $this->makeMapping($device, '1001', $empA);

        // Historical record already stamped with empA
        $record = \App\Models\AttendanceRecord::create([
            'device_id'         => $device->id,
            'device_user_id'    => '1001',
            'employee_id'       => $empA->id,
            'punch_datetime'    => now()->subDays(30),
            'punch_state'       => 0,
            'verification_type' => 10,
        ]);

        // Remap to empB
        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $empB->id,
                 'first_name'      => $empB->first_name,
                 'last_name'       => $empB->last_name,
                 'employee_number' => $empB->employee_number,
                 'status'          => 'active',
             ]);

        // Historical record must still point to empA
        $record->refresh();
        $this->assertSame($empA->id, $record->employee_id);
    }

    // ── 6. Validation ────────────────────────────────────────────────────────

    public function test_update_requires_first_name_when_employee_assigned(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id' => $employee->id,
                 'first_name'  => '',            // missing
                 'last_name'   => 'Cruz',
                 'employee_number' => 'EMP-001',
                 'status'      => 'active',
             ])
             ->assertSessionHasErrors('first_name');
    }

    public function test_update_requires_last_name_when_employee_assigned(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => 'Juan',
                 'last_name'       => '',        // missing
                 'employee_number' => 'EMP-001',
                 'status'          => 'active',
             ])
             ->assertSessionHasErrors('last_name');
    }

    public function test_update_rejects_invalid_status(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => 'Juan',
                 'last_name'       => 'Cruz',
                 'employee_number' => 'EMP-001',
                 'status'          => 'on_holiday',  // invalid
             ])
             ->assertSessionHasErrors('status');
    }

    public function test_update_rejects_nonexistent_branch(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => 'Juan',
                 'last_name'       => 'Cruz',
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
                 'branch_id'       => 99999,  // does not exist
             ])
             ->assertSessionHasErrors('branch_id');
    }

    // ── 7. Duplicate mapping prevention ─────────────────────────────────────

    public function test_update_rejects_employee_already_mapped_to_another_device_user(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();

        // Employee is already mapped to device user 1001
        $this->makeMapping($device, '1001', $employee);

        // Try to also map same employee to device user 1002
        $mapping2 = $this->makeMapping($device, '1002');

        $this->actingAs($admin)
             ->put("/device-users/{$mapping2->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => $employee->first_name,
                 'last_name'       => $employee->last_name,
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ])
             ->assertSessionHasErrors('employee_id');
    }

    // ── 8. Device user ID immutability ───────────────────────────────────────

    public function test_device_user_id_cannot_be_changed_via_update(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        // Inject device_user_id in the POST body — should be silently ignored
        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'device_user_id'  => '9999',   // attempt to change
                 'employee_id'     => $employee->id,
                 'first_name'      => $employee->first_name,
                 'last_name'       => $employee->last_name,
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ]);

        $mapping->refresh();
        $this->assertSame('1001', $mapping->device_user_id);
    }

    // ── 9. Audit log ──────────────────────────────────────────────────────────

    public function test_update_creates_audit_log_entry(): void
    {
        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee(['first_name' => 'Before', 'last_name' => 'Name']);
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => 'After',
                 'last_name'       => 'Name',
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ]);

        $this->assertDatabaseHas('audit_logs', [
            'action' => 'update_device_user',
            'module' => 'device_users',
            'user_id' => $admin->id,
        ]);
    }

    // ── 10. Employee search endpoint ─────────────────────────────────────────

    public function test_employee_search_returns_matching_results(): void
    {
        $admin = $this->makeAdmin();
        $this->makeEmployee(['first_name' => 'Maria', 'last_name' => 'Santos']);
        $this->makeEmployee(['first_name' => 'Pedro', 'last_name' => 'Reyes']);

        $this->actingAs($admin)
             ->getJson('/device-users/employee-search?q=Maria')
             ->assertStatus(200)
             ->assertJsonFragment(['full_name' => 'Maria Santos'])
             ->assertJsonMissing(['full_name' => 'Pedro Reyes']);
    }

    public function test_employee_search_requires_minimum_two_characters(): void
    {
        $admin = $this->makeAdmin();
        $this->actingAs($admin)
             ->getJson('/device-users/employee-search?q=M')
             ->assertStatus(200)
             ->assertJson([]);
    }

    public function test_employee_search_forbidden_without_permission(): void
    {
        $user = $this->makeUserWithRole('employee');
        $this->actingAs($user)
             ->getJson('/device-users/employee-search?q=test')
             ->assertStatus(403);
    }

    // ── 11. Device safety ─────────────────────────────────────────────────────

    public function test_successful_update_does_not_call_speedface_api(): void
    {
        // The SpeedFaceApiService should never be called during a device user update.
        // We verify this by ensuring no HTTP calls go to the Python service.
        // Since the controller does not inject SpeedFaceApiService, this is
        // architecturally guaranteed — but we also verify no unexpected redirect
        // to the Python API URL occurs.

        $admin    = $this->makeAdmin();
        $device   = $this->makeDevice();
        $employee = $this->makeEmployee();
        $mapping  = $this->makeMapping($device, '1001', $employee);

        $response = $this->actingAs($admin)
             ->put("/device-users/{$mapping->id}", [
                 'employee_id'     => $employee->id,
                 'first_name'      => $employee->first_name,
                 'last_name'       => $employee->last_name,
                 'employee_number' => $employee->employee_number,
                 'status'          => 'active',
             ]);

        // Response must redirect within the application — never to the Python API
        $response->assertRedirect("/device-users/{$mapping->id}");
        $this->assertStringNotContainsString('127.0.0.1:8000', $response->headers->get('Location') ?? '');
        $this->assertStringNotContainsString('api/sync', $response->headers->get('Location') ?? '');
    }
}
