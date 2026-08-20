@extends('layouts.app')
@section('title', 'Employees')

@section('content')

<div class="d-flex align-items-center justify-content-between mb-3">
    <h4 class="mb-0 fw-semibold"><i class="bi bi-people me-2 text-primary"></i>Employees</h4>
    <span class="text-muted small">Foundation — full HR management in a later phase</span>
</div>

@if($employees->isEmpty())
    <div class="card border-0 shadow-sm">
        <div class="card-body text-center py-5 text-muted">
            <i class="bi bi-people fs-1 opacity-25 d-block mb-2"></i>
            No employees registered yet.
        </div>
    </div>
@else
<div class="card border-0 shadow-sm">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>Employee #</th><th>Name</th><th>Department</th>
                    <th>Branch</th><th>Status</th><th></th>
                </tr>
            </thead>
            <tbody>
            @foreach($employees as $emp)
            <tr>
                <td class="small text-muted">{{ $emp->employee_number }}</td>
                <td class="fw-semibold">{{ $emp->full_name }}</td>
                <td class="small">{{ $emp->department?->name ?? '—' }}</td>
                <td class="small">{{ $emp->branch?->name ?? '—' }}</td>
                <td>
                    <span class="badge bg-{{ $emp->status === 'active' ? 'success' : 'secondary' }}">
                        {{ ucfirst($emp->status) }}
                    </span>
                </td>
                <td>
                    <a href="{{ route('employees.show', $emp) }}" class="btn btn-sm btn-outline-primary">
                        <i class="bi bi-eye"></i>
                    </a>
                </td>
            </tr>
            @endforeach
            </tbody>
        </table>
    </div>
    <div class="card-footer bg-white">{{ $employees->links() }}</div>
</div>
@endif

@endsection
