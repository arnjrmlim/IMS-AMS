@extends('layouts.app')
@section('title', 'Device User ' . $deviceUser->device_user_id)

@section('content')

<div class="d-flex align-items-center gap-2 mb-3">
    <a href="{{ route('device-users.index') }}" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-arrow-left"></i>
    </a>
    <h4 class="mb-0 fw-semibold">
        <i class="bi bi-person-badge me-1 text-primary"></i>
        Device User <code>{{ $deviceUser->device_user_id }}</code>
    </h4>
    @php
        $badgeColor = match($deviceUser->mapping_status) {
            'mapped'  => 'success',
            'ignored' => 'warning',
            default   => 'secondary',
        };
    @endphp
    <span class="badge bg-{{ $badgeColor }}">{{ ucfirst($deviceUser->mapping_status) }}</span>

    @can('manage_device_users')
    <a href="{{ route('device-users.edit', $deviceUser) }}"
       class="btn btn-sm btn-primary ms-auto">
        <i class="bi bi-pencil me-1"></i>Edit Information
    </a>
    @endcan
</div>

{{-- READ-ONLY notice --}}
<div class="alert alert-success border-0 py-2 mb-3 small">
    <i class="bi bi-shield-check me-1"></i>
    <strong>READ ONLY</strong> — The SpeedFace-V5L is never modified by this system.
    Changes made here affect only the application database.
</div>

<div class="row g-3">

    {{-- ── Column 1: Device Information ─────────────────────────────────── --}}
    <div class="col-md-6">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">
                <i class="bi bi-cpu me-1 text-secondary"></i> Device Source Information
                <span class="text-muted fw-normal small ms-1">(read-only — from SpeedFace)</span>
            </div>
            <div class="card-body pt-0">
                <table class="table table-sm">
                    <tr>
                        <td class="text-muted" style="width:45%">Device User ID</td>
                        <td><code class="fw-semibold fs-6">{{ $deviceUser->device_user_id }}</code></td>
                    </tr>
                    <tr>
                        <td class="text-muted">Device</td>
                        <td>{{ $deviceUser->device?->name ?? '—' }}</td>
                    </tr>
                    <tr>
                        <td class="text-muted">Device Model</td>
                        <td>{{ $deviceUser->device?->model ?? '—' }}</td>
                    </tr>
                    <tr>
                        <td class="text-muted">Device IP</td>
                        <td>{{ $deviceUser->device?->ip_address ?? '—' }}</td>
                    </tr>
                    <tr>
                        <td class="text-muted">Source Name</td>
                        <td>{{ $deviceUser->device_name ?? '—' }}
                            <span class="text-muted small">(from device)</span>
                        </td>
                    </tr>
                    <tr>
                        <td class="text-muted">Last Device Sync</td>
                        <td>
                            {{ $deviceUser->device?->last_sync_at
                                ? $deviceUser->device->last_sync_at
                                    ->setTimezone(config('app.timezone', 'UTC'))
                                    ->format('M d, Y H:i')
                                : '—' }}
                        </td>
                    </tr>
                    <tr>
                        <td class="text-muted">Mapping Status</td>
                        <td>
                            <span class="badge bg-{{ $badgeColor }}">
                                {{ ucfirst($deviceUser->mapping_status) }}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>

    {{-- ── Column 2: Application Information ─────────────────────────────── --}}
    <div class="col-md-6">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">
                <i class="bi bi-person me-1 text-secondary"></i> Application Information
                <span class="text-muted fw-normal small ms-1">(editable — application database)</span>
            </div>
            <div class="card-body pt-0">
                @if($deviceUser->employee)
                    @php $emp = $deviceUser->employee; @endphp
                    <table class="table table-sm">
                        <tr>
                            <td class="text-muted" style="width:45%">Employee Number</td>
                            <td>{{ $emp->employee_number }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">First Name</td>
                            <td>{{ $emp->first_name }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Middle Name</td>
                            <td>{{ $emp->middle_name ?? '—' }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Last Name</td>
                            <td>{{ $emp->last_name }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Suffix</td>
                            <td>{{ $emp->suffix ?? '—' }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Branch</td>
                            <td>{{ $emp->branch?->name ?? '—' }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Department</td>
                            <td>{{ $emp->department?->name ?? '—' }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Employee Status</td>
                            <td>
                                <span class="badge bg-{{ $emp->status === 'active' ? 'success' : 'secondary' }}">
                                    {{ ucfirst($emp->status) }}
                                </span>
                            </td>
                        </tr>
                    </table>
                @else
                    <div class="text-center py-4">
                        <i class="bi bi-person-x fs-2 opacity-25 d-block mb-2"></i>
                        <p class="text-muted mb-3">No employee assigned to this device user.</p>
                        @can('manage_device_users')
                        <a href="{{ route('device-users.edit', $deviceUser) }}"
                           class="btn btn-sm btn-primary">
                            <i class="bi bi-person-plus me-1"></i>Assign Employee
                        </a>
                        @endcan
                    </div>
                @endif
            </div>
        </div>
    </div>

    {{-- ── Recent Attendance ────────────────────────────────────────────── --}}
    <div class="col-12">
        <div class="card border-0 shadow-sm">
            <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">
                <i class="bi bi-clock-history me-1 text-secondary"></i> Recent Attendance
                <span class="text-muted fw-normal small ms-1">(last 10 records)</span>
            </div>
            <div class="card-body p-0">
                @if($recentAttendance->isEmpty())
                    <div class="text-center py-4 text-muted small">
                        No attendance records found for this device user.
                    </div>
                @else
                <div class="table-responsive">
                    <table class="table table-sm table-hover align-middle mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Date</th>
                                <th>Time</th>
                                <th>Punch</th>
                                <th>Verification</th>
                            </tr>
                        </thead>
                        <tbody>
                        @foreach($recentAttendance as $rec)
                            @php
                                $dt = \Carbon\Carbon::parse($rec->punch_datetime)
                                    ->setTimezone(config('app.timezone', 'UTC'));
                                $stateColor = match($rec->punch_state_label) {
                                    'Check In'  => 'success',
                                    'Check Out' => 'secondary',
                                    default     => 'info',
                                };
                            @endphp
                            <tr>
                                <td class="small">{{ $dt->format('M d, Y') }}</td>
                                <td class="fw-semibold">{{ $dt->format('H:i:s') }}</td>
                                <td>
                                    <span class="badge bg-{{ $stateColor }}">
                                        {{ $rec->punch_state_label ?? 'State '.$rec->punch_state }}
                                    </span>
                                </td>
                                <td class="small text-muted">
                                    {{ $rec->verification_type_label ?? 'Unknown' }}
                                </td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                </div>
                @endif
            </div>
        </div>
    </div>

</div>

@endsection
