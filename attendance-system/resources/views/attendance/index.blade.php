@extends('layouts.app')
@section('title', 'Attendance Records')

@section('content')

@if(! $apiOnline)
<div class="api-offline-banner mb-3">
    <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
    <strong>Integration service is offline.</strong>
    Attendance records cannot be retrieved.
    Run <code>python run.py serve</code> in the <code>speedface-integration</code> directory.
</div>
@endif

<div class="d-flex align-items-center justify-content-between mb-3">
    <h4 class="mb-0 fw-semibold"><i class="bi bi-clock-history me-2 text-primary"></i>Attendance Records</h4>
    <span class="text-muted small">No business calculations — raw punch data only</span>
</div>

{{-- Filter form --}}
<div class="card border-0 shadow-sm mb-3">
    <div class="card-body py-3">
        <form method="GET" action="{{ route('attendance.index') }}" class="row g-2 align-items-end">
            <div class="col-md-2">
                <label class="form-label small mb-1">Device</label>
                <select name="device_id" class="form-select form-select-sm">
                    <option value="">All Devices</option>
                    @foreach($devices as $device)
                        <option value="{{ $device->id }}" {{ ($filters['device_id'] ?? '') == $device->id ? 'selected' : '' }}>
                            {{ $device->name ?? 'Device #'.$device->id }}
                        </option>
                    @endforeach
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-1">Device User ID</label>
                <input type="text" name="device_user_id" class="form-control form-control-sm"
                    value="{{ $filters['device_user_id'] ?? '' }}" placeholder="e.g. 1001">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-1">Date From</label>
                <input type="date" name="date_from" class="form-control form-control-sm"
                    value="{{ request('date_from') }}">
            </div>
            <div class="col-md-2">
                <label class="form-label small mb-1">Date To</label>
                <input type="date" name="date_to" class="form-control form-control-sm"
                    value="{{ request('date_to') }}">
            </div>
            <div class="col-md-1">
                <label class="form-label small mb-1">Per Page</label>
                <select name="per_page" class="form-select form-select-sm">
                    @foreach([25, 50, 100] as $pp)
                        <option value="{{ $pp }}" {{ $perPage == $pp ? 'selected' : '' }}>{{ $pp }}</option>
                    @endforeach
                </select>
            </div>
            <div class="col-md-3 d-flex gap-2">
                <button type="submit" class="btn btn-sm btn-primary">
                    <i class="bi bi-search me-1"></i>Filter
                </button>
                <a href="{{ route('attendance.index') }}" class="btn btn-sm btn-outline-secondary">
                    <i class="bi bi-x"></i> Clear
                </a>
            </div>
        </form>
    </div>
</div>

{{-- Records table --}}
<div class="card border-0 shadow-sm">
    @if($errorMsg)
        <div class="card-body text-center py-5">
            <i class="bi bi-exclamation-triangle fs-1 text-warning d-block mb-2 opacity-50"></i>
            <p class="text-muted">{{ $errorMsg }}</p>
        </div>
    @elseif(empty($records))
        <div class="card-body text-center py-5 text-muted">
            <i class="bi bi-clock-history fs-1 opacity-25 d-block mb-2"></i>
            No attendance records found for the selected filters.
        </div>
    @else
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Device User ID</th>
                    <th>Punch State</th>
                    <th>Verification</th>
                </tr>
            </thead>
            <tbody>
            @foreach($records as $rec)
                @php
                    $dt = \Carbon\Carbon::parse($rec['punch_datetime'])->timezone(config('app.timezone'));
                    $stateLabel = $rec['punch_state_label'] ?? match((int)($rec['punch_state'] ?? 0)) {
                        0 => 'Check In', 1 => 'Check Out', 2 => 'Break Out',
                        3 => 'Break In', 4 => 'Overtime In', 5 => 'Overtime Out',
                        default => 'State '.($rec['punch_state'] ?? '?'),
                    };
                    $verifyLabel = $rec['verification_type_label'] ?? 'Unknown';
                    $stateColor = match($stateLabel) {
                        'Check In' => 'success', 'Check Out' => 'secondary',
                        'Overtime In', 'Overtime Out' => 'warning',
                        default => 'info'
                    };
                @endphp
                <tr>
                    <td class="small">{{ $dt->format('M d, Y') }}</td>
                    <td class="fw-semibold">{{ $dt->format('H:i:s') }}</td>
                    <td><code>{{ $rec['device_user_id'] }}</code></td>
                    <td><span class="badge bg-{{ $stateColor }}">{{ $stateLabel }}</span></td>
                    <td class="small text-muted">
                        <i class="bi bi-{{ str_contains(strtolower($verifyLabel), 'face') ? 'emoji-smile' : (str_contains(strtolower($verifyLabel), 'card') ? 'credit-card' : 'fingerprint') }} me-1"></i>
                        {{ $verifyLabel }}
                    </td>
                </tr>
            @endforeach
            </tbody>
        </table>
    </div>

    {{-- Pagination --}}
    @if(! empty($meta))
    <div class="card-footer bg-white d-flex align-items-center justify-content-between flex-wrap gap-2">
        <small class="text-muted">
            Showing {{ number_format(($meta['page'] - 1) * $meta['per_page'] + 1) }}–{{ number_format(min($meta['page'] * $meta['per_page'], $meta['total'])) }}
            of {{ number_format($meta['total']) }} records
        </small>
        <nav>
            <ul class="pagination pagination-sm mb-0">
                @if($meta['page'] > 1)
                    <li class="page-item">
                        <a class="page-link" href="{{ request()->fullUrlWithQuery(['page' => $meta['page'] - 1]) }}">‹ Prev</a>
                    </li>
                @endif
                <li class="page-item disabled">
                    <span class="page-link">Page {{ $meta['page'] }} of {{ $meta['pages'] }}</span>
                </li>
                @if($meta['page'] < $meta['pages'])
                    <li class="page-item">
                        <a class="page-link" href="{{ request()->fullUrlWithQuery(['page' => $meta['page'] + 1]) }}">Next ›</a>
                    </li>
                @endif
            </ul>
        </nav>
    </div>
    @endif
    @endif
</div>

@endsection
