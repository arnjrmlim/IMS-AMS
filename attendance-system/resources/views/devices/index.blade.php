@extends('layouts.app')
@section('title', 'Devices')

@section('content')

@if(! $apiOnline)
<div class="api-offline-banner mb-3">
    <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
    <strong>Integration service is offline.</strong> Device status may be stale.
    Run <code>python run.py serve</code> in the <code>speedface-integration</code> directory.
</div>
@endif

<div class="d-flex align-items-center justify-content-between mb-3">
    <h4 class="mb-0 fw-semibold"><i class="bi bi-cpu me-2 text-primary"></i>Devices</h4>
    <span class="badge bg-{{ $apiOnline ? 'success' : 'secondary' }}">
        Integration: {{ $apiOnline ? 'Online' : 'Offline' }}
    </span>
</div>

@if($devices->isEmpty())
    <div class="card border-0 shadow-sm">
        <div class="card-body text-center py-5 text-muted">
            <i class="bi bi-cpu fs-1 opacity-25 d-block mb-2"></i>
            No devices registered yet.
            Run <code>python run.py sync</code> to synchronise device information.
        </div>
    </div>
@else
<div class="row g-3">
@foreach($devices as $device)
    <div class="col-md-6 col-xl-4">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="fw-semibold mb-0">{{ $device->name ?? 'SpeedFace Device' }}</h6>
                    <span class="badge bg-{{ $device->status_badge }}">{{ ucfirst($device->status) }}</span>
                </div>
                <table class="table table-sm table-borderless mb-0 small">
                    <tr><td class="text-muted">Serial</td><td>{{ $device->serial_number ?? '—' }}</td></tr>
                    <tr><td class="text-muted">IP Address</td><td><code>{{ $device->ip_address ?? '—' }}:{{ $device->port }}</code></td></tr>
                    <tr><td class="text-muted">Firmware</td><td>{{ $device->firmware_version ?? '—' }}</td></tr>
                    <tr><td class="text-muted">Platform</td><td>{{ $device->platform ?? '—' }}</td></tr>
                    <tr><td class="text-muted">Users</td><td>{{ $device->user_count !== null ? number_format($device->user_count) : '—' }}</td></tr>
                    <tr><td class="text-muted">Records</td><td>{{ $device->attendance_count !== null ? number_format($device->attendance_count) : '—' }}</td></tr>
                    <tr><td class="text-muted">Last Sync</td>
                        <td>{{ $device->last_sync_at ? \Carbon\Carbon::parse($device->last_sync_at)->timezone(config('app.timezone'))->format('M d, Y H:i') : '—' }}</td></tr>
                </table>
            </div>
            <div class="card-footer bg-white border-top-0 pt-0 pb-3">
                <a href="{{ route('devices.show', $device) }}" class="btn btn-sm btn-outline-primary me-1">
                    <i class="bi bi-info-circle me-1"></i>Details
                </a>
                @can('manage_devices')
                <button class="btn btn-sm btn-outline-secondary refresh-btn" data-device-id="{{ $device->id }}" data-url="{{ route('devices.refresh', $device) }}">
                    <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                </button>
                @endcan
            </div>
        </div>
    </div>
@endforeach
</div>
@endif

@endsection

@push('scripts')
<script>
document.querySelectorAll('.refresh-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        this.disabled = true;
        this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Refreshing...';
        fetch(this.dataset.url, {
            method: 'POST',
            headers: {'X-CSRF-TOKEN': document.querySelector('meta[name=csrf-token]').content, 'Accept': 'application/json'}
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) { location.reload(); }
            else { alert(data.message || 'Refresh failed.'); this.disabled = false; this.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh'; }
        })
        .catch(() => { alert('Could not reach the server.'); this.disabled = false; this.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh'; });
    });
});
</script>
@endpush
