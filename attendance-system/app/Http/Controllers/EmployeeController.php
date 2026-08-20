<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Branch;
use App\Models\Department;
use App\Models\Employee;
use Illuminate\View\View;

class EmployeeController extends Controller
{
    public function index(): View
    {
        $employees = Employee::with(['branch', 'department'])
            ->orderBy('last_name')
            ->orderBy('first_name')
            ->paginate(25);

        return view('employees.index', compact('employees'));
    }

    public function show(Employee $employee): View
    {
        $employee->load(['branch', 'department', 'deviceMappings.device']);
        return view('employees.show', compact('employee'));
    }
}
