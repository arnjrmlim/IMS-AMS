<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Http\Requests\UpdateDeviceUserRequest;
use App\Models\Branch;
use App\Models\Department;
use App\Models\Device;
use App\Models\DeviceUserMapping;
use App\Models\Employee;
use App\Services\AuditService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\View\View;

/**
 * Device User Mapping — Phase 4A
 *
 * Manages the application-side mapping between SpeedFace device users
 * and application employees. Never communicates with the SpeedFace device.
 *
 * READ-ONLY DEVICE POLICY
 * -----------------------
 * This controller only reads device user data that was already synced by
 * the Python integration service. It NEVER:
 *   - calls any SpeedFace write/delete API
 *   - modifies data on port 4370
 *   - pushes changes back through the Python service
 *
 * All changes are confined to the Laravel application database.
 */
class DeviceUserMappingController extends Controller
{
    // ── Index — list + search ───────────────────────────────────────────────

    public function index(Request $request): View
    {
        $query = DeviceUserMapping::with(['device', 'employee.branch', 'employee.department'])
            ->orderBy('device_id')
            ->orderBy('device_user_id');

        // Filter: device user ID (primary search)
        if ($search = $request->input('device_user_id')) {
            $query->where('device_user_id', 'like', '%'.trim($search).'%');
        }

        // Filter: employee name or employee number (general search)
        if ($name = $request->input('search')) {
            $query->where(function ($q) use ($name): void {
                $q->where('device_name', 'like', '%'.trim($name).'%')
                  ->orWhereHas('employee', function ($eq) use ($name): void {
                      $eq->where('first_name',       'like', '%'.trim($name).'%')
                         ->orWhere('last_name',       'like', '%'.trim($name).'%')
                         ->orWhere('employee_number', 'like', '%'.trim($name).'%');
                  });
            });
        }

        // Filter: device
        if ($deviceId = $request->input('device_id')) {
            $query->where('device_id', $deviceId);
        }

        // Filter: mapping status
        if ($status = $request->input('mapping_status')) {
            $query->where('mapping_status', $status);
        }

        $mappings = $query->paginate(25)->withQueryString();
        $devices  = Device::orderBy('name')->get();

        AuditService::log('view_device_users', 'Viewed device users list.', 'device_users');

        return view('device-users.index', compact('mappings', 'devices'));
    }

    // ── Show — detail page ──────────────────────────────────────────────────

    public function show(DeviceUserMapping $deviceUser): View
    {
        $deviceUser->load(['device.branch', 'employee.branch', 'employee.department']);

        // Recent attendance records for this device user (last 10)
        $recentAttendance = $deviceUser->device
            ? \App\Models\AttendanceRecord::where('device_id', $deviceUser->device_id)
                ->where('device_user_id', $deviceUser->device_user_id)
                ->orderByDesc('punch_datetime')
                ->limit(10)
                ->get()
            : collect();

        AuditService::log(
            'view_device_user',
            "Viewed device user {$deviceUser->device_user_id} on device {$deviceUser->device?->name}.",
            'device_users',
            ['mapping_id' => $deviceUser->id]
        );

        return view('device-users.show', compact('deviceUser', 'recentAttendance'));
    }

    // ── Edit — form ─────────────────────────────────────────────────────────

    public function edit(DeviceUserMapping $deviceUser): View
    {
        $deviceUser->load(['device', 'employee.branch', 'employee.department']);

        $branches    = Branch::where('is_active', true)->orderBy('name')->get();
        $departments = Department::where('is_active', true)->orderBy('name')->get();

        return view('device-users.edit', compact('deviceUser', 'branches', 'departments'));
    }

    // ── Update — save ───────────────────────────────────────────────────────

    public function update(UpdateDeviceUserRequest $request, DeviceUserMapping $deviceUser): RedirectResponse
    {
        $validated = $request->validated();

        // Snapshot before-state for audit log
        $before = $this->snapshotMapping($deviceUser);

        DB::transaction(function () use ($validated, $deviceUser): void {

            $employeeId = $validated['employee_id'] ?? null;

            // ── Employee information update ─────────────────────────────────
            // If an employee is being assigned or is already mapped, update their
            // application record. Never touches the SpeedFace device.
            if ($employeeId) {
                $employee = Employee::findOrFail($employeeId);

                $employeeData = array_filter([
                    'first_name'        => $validated['first_name']        ?? null,
                    'middle_name'       => $validated['middle_name']       ?? null,
                    'last_name'         => $validated['last_name']         ?? null,
                    'suffix'            => $validated['suffix']            ?? null,
                    'employee_number'   => $validated['employee_number']   ?? null,
                    'branch_id'         => $validated['branch_id']         ?? null,
                    'department_id'     => $validated['department_id']     ?? null,
                    'status'            => $validated['status']            ?? null,
                ], fn ($v) => $v !== null);

                if (! empty($employeeData)) {
                    $employee->update($employeeData);
                }
            }

            // ── Mapping update ──────────────────────────────────────────────
            $previousEmployeeId = $deviceUser->employee_id;
            $isNewMapping       = ($employeeId !== null && (int) $previousEmployeeId !== (int) $employeeId);

            $deviceUser->update([
                'employee_id'    => $employeeId,
                'mapping_status' => $employeeId ? 'mapped' : 'unmapped',
            ]);

            // ── Sync employee_id onto attendance records ────────────────────
            // When a new employee is mapped, stamp their employee_id onto existing
            // attendance records for this device+user pair so they become traceable.
            // Historical records for a PREVIOUS employee are left intact —
            // they retain the original employee_id and remain fully traceable.
            if ($isNewMapping && $employeeId) {
                \App\Models\AttendanceRecord::where('device_id', $deviceUser->device_id)
                    ->where('device_user_id', $deviceUser->device_user_id)
                    ->whereNull('employee_id')   // only stamp previously-unmapped records
                    ->update(['employee_id' => $employeeId]);
            }
        });

        // ── Audit log with before/after diff ───────────────────────────────
        $deviceUser->refresh()->load(['device', 'employee']);
        $after = $this->snapshotMapping($deviceUser);

        $changes = $this->buildChangeset($before, $after);

        AuditService::log(
            'update_device_user',
            "Updated device user {$deviceUser->device_user_id} on device {$deviceUser->device?->name}.",
            'device_users',
            [
                'mapping_id'     => $deviceUser->id,
                'device_user_id' => $deviceUser->device_user_id,
                'changes'        => $changes,
            ]
        );

        return redirect()
            ->route('device-users.show', $deviceUser)
            ->with('success', 'Device user information updated successfully. No changes were made to the SpeedFace device.');
    }

    // ── Employee search (JSON — for the live search input) ──────────────────

    public function employeeSearch(Request $request): JsonResponse
    {
        $term = trim($request->input('q', ''));

        if (strlen($term) < 2) {
            return response()->json([]);
        }

        $employees = Employee::with(['branch', 'department'])
            ->where(function ($q) use ($term): void {
                $q->where('first_name',       'like', "%{$term}%")
                  ->orWhere('last_name',       'like', "%{$term}%")
                  ->orWhere('employee_number', 'like', "%{$term}%");
            })
            ->where('status', 'active')
            ->orderBy('last_name')
            ->orderBy('first_name')
            ->limit(20)
            ->get();

        return response()->json(
            $employees->map(fn (Employee $e) => [
                'id'              => $e->id,
                'full_name'       => $e->full_name,
                'employee_number' => $e->employee_number,
                'department'      => $e->department?->name,
                'branch'          => $e->branch?->name,
            ])
        );
    }

    // ── Private helpers ─────────────────────────────────────────────────────

    /**
     * Build a flat snapshot of mapping + linked employee for audit diff.
     */
    private function snapshotMapping(DeviceUserMapping $mapping): array
    {
        $emp = $mapping->employee;
        return [
            'employee_id'     => $mapping->employee_id,
            'mapping_status'  => $mapping->mapping_status,
            'employee_number' => $emp?->employee_number,
            'first_name'      => $emp?->first_name,
            'middle_name'     => $emp?->middle_name,
            'last_name'       => $emp?->last_name,
            'suffix'          => $emp?->suffix,
            'branch_id'       => $emp?->branch_id,
            'department_id'   => $emp?->department_id,
            'status'          => $emp?->status,
        ];
    }

    /**
     * Return only the keys that changed between before and after snapshots.
     * Format: ['field' => ['old' => x, 'new' => y]]
     */
    private function buildChangeset(array $before, array $after): array
    {
        $changes = [];
        foreach ($after as $key => $newVal) {
            $oldVal = $before[$key] ?? null;
            // Loose comparison is intentional — int vs string IDs
            if ((string) $oldVal !== (string) $newVal) {
                $changes[$key] = ['old' => $oldVal, 'new' => $newVal];
            }
        }
        return $changes;
    }
}
