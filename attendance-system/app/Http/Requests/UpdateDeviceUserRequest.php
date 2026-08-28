<?php

declare(strict_types=1);

namespace App\Http\Requests;

use App\Models\DeviceUserMapping;
use App\Models\Employee;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Server-side validation for updating a device user mapping and its linked
 * application employee record.
 *
 * SAFETY: device_user_id is never accepted from the request — it is always
 * read from the route-bound model and never overwritten.
 */
class UpdateDeviceUserRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->hasPermission('manage_device_users') ?? false;
    }

    public function rules(): array
    {
        /** @var DeviceUserMapping $mapping */
        $mapping    = $this->route('deviceUser');
        $employeeId = $this->input('employee_id');

        // If an employee_id is being assigned, the employee-level fields are
        // required; if no employee is assigned, only the mapping is updated.
        $employeePresent = ! empty($employeeId);

        // Existing employee_id being kept (for unique-ignore logic on employee_number)
        // Ignore the employee currently being assigned (submitted) so their own
        // employee_number doesn't trigger the unique violation against themselves.
        $submittedEmployeeId = $this->input('employee_id') ?? $mapping->employee_id;

        return [
            // ── Mapping ────────────────────────────────────────────────────
            'employee_id' => [
                'nullable',
                'integer',
                Rule::exists('employees', 'id'),
                // Prevent assigning an employee already mapped to a DIFFERENT
                // device user on the same device.
                function (string $attribute, mixed $value, callable $fail) use ($mapping): void {
                    if (! $value) {
                        return;
                    }
                    $conflict = DeviceUserMapping::where('device_id',     $mapping->device_id)
                        ->where('employee_id',    $value)
                        ->where('id',             '!=', $mapping->id)
                        ->where('mapping_status', 'mapped')
                        ->first();

                    if ($conflict) {
                        $emp  = Employee::find($value);
                        $name = $emp?->full_name ?? "Employee #{$value}";
                        $fail("{$name} is already assigned to Device User ID {$conflict->device_user_id} on this device.");
                    }
                },
            ],

            // ── Employee fields (required when employee is being assigned) ─
            'first_name' => [
                $employeePresent ? 'required' : 'nullable',
                'string', 'max:80',
            ],
            'middle_name' => [
                'nullable', 'string', 'max:80',
            ],
            'last_name' => [
                $employeePresent ? 'required' : 'nullable',
                'string', 'max:80',
            ],
            'suffix' => [
                'nullable', 'string', 'max:10',
            ],
            'employee_number' => [
                $employeePresent ? 'required' : 'nullable',
                'string', 'max:30',
                // Unique across employees, but ignore the employee being assigned
                // so their existing employee_number doesn't conflict with itself.
                Rule::unique('employees', 'employee_number')
                    ->ignore($submittedEmployeeId ?? 0),
            ],
            'branch_id' => [
                'nullable', 'integer',
                Rule::exists('branches', 'id'),
            ],
            'department_id' => [
                'nullable', 'integer',
                Rule::exists('departments', 'id'),
            ],
            'status' => [
                $employeePresent ? 'required' : 'nullable',
                Rule::in(['active', 'inactive', 'resigned']),
            ],
        ];
    }

    public function messages(): array
    {
        return [
            'first_name.required'      => 'First name is required when assigning an employee.',
            'last_name.required'       => 'Last name is required when assigning an employee.',
            'employee_number.required' => 'Employee number is required when assigning an employee.',
            'employee_number.unique'   => 'This employee number is already in use by another employee.',
            'status.required'          => 'Status is required when assigning an employee.',
            'status.in'                => 'Status must be Active, Inactive, or Resigned.',
            'branch_id.exists'         => 'The selected branch does not exist.',
            'department_id.exists'     => 'The selected department does not exist.',
            'employee_id.exists'       => 'The selected employee does not exist.',
        ];
    }
}
