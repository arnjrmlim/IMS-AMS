@extends('layouts.app')
@section('title', 'Device Users')

@section('content')

@if(! $apiOnline)
<div class="api-offline-banner mb-3">
    <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
    <strong>Integration service is offline.</strong>
    Device users cannot be refreshed from the device.
    Run <code>python run.py serve</code> in the <code>speedface-integration</code> directory.
</div>
@endif

<div class="d-flex align-items-center justify-content-between mb-3">
    <h4 class="mb-0 fw-semibold">
        <i class="bi bi-person-badge me-2 text-primary"></i>Device Users
    </h4>
    <span class="text-muted small">
        <i class="bi bi-shield-check me-1 text-success"></i>
        Application-side mapping only — SpeedFace device is never modified
    </span>
</div>

{{-- Filter form --}}
<div class="card border-0 shadow-sm mb-3">
    <div class="card-body py-3">
        <form method="GET" action="{{ route('device-users.index') }}" class="row g-2 align-items-end">

            <div class="col-md-2">
                <label class="form-label small mb-1">Device User ID</label>
                <input type="text" name="device_user_id" class="form-control form-control-sm"
                       value="{{ request('device_user_id') }}" placeholder="e.g. 1001">
            </div>

            <div class="col-md-3">
                <label class="form-label small mb-1">Name / Employee No.</label>
                <input type="text" name="search" class="form-control form-control-sm"
                       value="{{ request('search') }}" placeholder="Search name or employee #">
            </div>

            <div class="col-md-2">
                <label class="form-label small mb-1">Device</label>
                <select name="device_id" class="form-select form-select-sm">
                    <option value="">All Devices</option>
                    @foreach($devices as $device)
                        <option value="{{ $device->id }}"
                            {{ request('device_id') == $device->id ? 'selected' : '' }}>
                            {{ $device->name ?? 'Device #'.$device->id }}
                        </option>
                    @endforeach
                </select>
            </div>

            <div class="col-md-2">
                <label class="form-label small mb-1">Mapping Status</label>
                <select name="mapping_status" class="form-select form-select-sm">
                    <option value="">All Statuses</option>
                    <option value="mapped"   {{ request('mapping_status') === 'mapped'   ? 'selected' : '' }}>Mapped</option>
                    <option value="unmapped" {{ request('mapping_status') === 'unmapped' ? 'selected' : '' }}>Unmapped</option>
                    <option value="ignored"  {{ request('mapping_status') === 'ignored'  ? 'selected' : '' }}>Ignored</option>
                </select>
            </div>

            <div class="col-md-3 d-flex gap-2">
                <button type="submit" class="btn btn-sm btn-primary">
                    <i class="bi bi-search me-1"></i>Filter
                </button>
                <a href="{{ route('device-users.index') }}" class="btn btn-sm btn-outline-secondary">
                    <i class="bi bi-x"></i> Clear
                </a>
            </div>

        </form>
    </div>
</div>

{{-- Results table --}}
<div class="card border-0 shadow-sm">
    @if($mappings->isEmpty())
        <div class="card-body text-center py-5 text-muted">
            <i class="bi bi-person-badge fs-1 opacity-25 d-block mb-2"></i>
            @if(request()->hasAny(['device_user_id', 'search', 'device_id', 'mapping_status']))
                No device users found matching the selected filters.
            @else
                No device users have been synchronised yet.
                <div class="mt-2 small">
                    Run a synchronisation from the
                    <a href="{{ route('sync.index') }}">Synchronisation</a> page first.
                </div>
            @endif
        </div>
    @else
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>Device User ID</th>
                    <th>Device Name (Source)</th>
                    <th>Device</th>
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Branch</th>
                    <th>Status</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
            @foreach($mappings as $mapping)
            <tr>
                <td><code class="fw-semibold">{{ $mapping->device_user_id }}</code></td>
                <td class="small text-muted">{{ $mapping->device_name ?? '—' }}</td>
                <td class="small">{{ $mapping->device?->name ?? '—' }}</td>
                <td>
                    @if($mapping->employee)
                        <span class="fw-semibold">{{ $mapping->employee->full_name }}</span>
                        <div class="text-muted small">{{ $mapping->employee->employee_number }}</div>
                    @else
                        <span class="text-muted fst-italic">Unassigned</span>
                    @endif
                </td>
                <td class="small">{{ $mapping->employee?->department?->name ?? '—' }}</td>
                <td class="small">{{ $mapping->employee?->branch?->name ?? '—' }}</td>
                <td>
                    @php
                        $badgeColor = match($mapping->mapping_status) {
                            'mapped'   => 'success',
                            'ignored'  => 'warning',
                            default    => 'secondary',
                        };
                    @endphp
                    <span class="badge bg-{{ $badgeColor }}">{{ ucfirst($mapping->mapping_status) }}</span>
                </td>
                <td>
                    <a href="{{ route('device-users.show', $mapping) }}"
                       class="btn btn-sm btn-outline-primary" title="View">
                        <i class="bi bi-eye"></i>
                    </a>
                    @can('manage_device_users')
                    <a href="{{ route('device-users.edit', $mapping) }}"
                       class="btn btn-sm btn-outline-secondary ms-1" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </a>
                    @endcan
                </td>
            </tr>
            @endforeach
            </tbody>
        </table>
    </div>

    {{-- Pagination --}}
    <div class="card-footer bg-white d-flex align-items-center justify-content-between flex-wrap gap-2">
        <small class="text-muted">
            Showing {{ $mappings->firstItem() }}–{{ $mappings->lastItem() }}
            of {{ number_format($mappings->total()) }} device users
        </small>
        {{ $mappings->links() }}
    </div>
    @endif
</div>

@endsection
