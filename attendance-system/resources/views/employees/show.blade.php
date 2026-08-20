@extends('layouts.app')
@section('title', $employee->full_name)

@section('content')

<div class="d-flex align-items-center gap-2 mb-3">
    <a href="{{ route('employees.index') }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-arrow-left"></i></a>
    <h4 class="mb-0 fw-semibold">{{ $employee->full_name }}</h4>
    <span class="badge bg-{{ $employee->status === 'active' ? 'success' : 'secondary' }}">{{ ucfirst($employee->status) }}</span>
</div>

<div class="row g-3">
    <div class="col-md-6">
        <div class="card border-0 shadow-sm">
            <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">Employee Information</div>
            <div class="card-body pt-0">
                <table class="table table-sm">
                    <tr><td class="text-muted" style="width:40%">Employee #</td><td>{{ $employee->employee_number }}</td></tr>
                    <tr><td class="text-muted">Full Name</td><td>{{ $employee->full_name }}</td></tr>
                    <tr><td class="text-muted">Position</td><td>{{ $employee->position ?? '—' }}</td></tr>
                    <tr><td class="text-muted">Department</td><td>{{ $employee->department?->name ?? '—' }}</td></tr>
                    <tr><td class="text-muted">Branch</td><td>{{ $employee->branch?->name ?? '—' }}</td></tr>
                    <tr><td class="text-muted">Date Hired</td><td>{{ $employee->date_hired?->format('M d, Y') ?? '—' }}</td></tr>
                    <tr><td class="text-muted">Email</td><td>{{ $employee->email ?? '—' }}</td></tr>
                </table>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card border-0 shadow-sm">
            <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">Device Mappings</div>
            <div class="card-body pt-0">
                @if($employee->deviceMappings->isEmpty())
                    <p class="text-muted small">No device mappings yet.</p>
                @else
                <table class="table table-sm">
                    <thead class="table-light"><tr><th>Device</th><th>Device User ID</th><th>Status</th></tr></thead>
                    <tbody>
                    @foreach($employee->deviceMappings as $mapping)
                    <tr>
                        <td>{{ $mapping->device?->name ?? '—' }}</td>
                        <td><code>{{ $mapping->device_user_id }}</code></td>
                        <td><span class="badge bg-{{ $mapping->mapping_status === 'mapped' ? 'success' : 'secondary' }}">{{ $mapping->mapping_status }}</span></td>
                    </tr>
                    @endforeach
                    </tbody>
                </table>
                @endif
            </div>
        </div>
    </div>
</div>

@endsection
