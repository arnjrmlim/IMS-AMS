@extends('layouts.app')
@section('title', $device->name ?? 'Device Details')

@section('content')

<div class="d-flex align-items-center gap-2 mb-3">
    <a href="{{ route('devices.index') }}" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-arrow-left"></i>
    </a>
    <h4 class="mb-0 fw-semibold"><i class="bi bi-cpu me-2 text-primary"></i>{{ $device->name ?? 'Device Details' }}</h4>
    <span class="badge bg-{{ $device->status_badge }}">{{ ucfirst($device->status) }}</span>
</div>

<div class="row g-3">
    <div class="col-md-6">
        <div class="card border-0 shadow-sm">
            <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">Device Information</div>
            <div class="card-body pt-0">
                <table class="table table-sm">
                    <tr><th class="text-muted fw-normal" style="width:40%">Name</th><td>{{ $device->name ?? '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">Model</th><td>{{ $device->model ?? '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">Serial Number</th><td>{{ $device->serial_number ?? '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">IP Address</th><td><code>{{ $device->ip_address ?? '—' }}:{{ $device->port }}</code></td></tr>
                    <tr><th class="text-muted fw-normal">Firmware</th><td>{{ $device->firmware_version ?? '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">Platform</th><td>{{ $device->platform ?? '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">User Count</th><td>{{ $device->user_count !== null ? number_format($device->user_count) : '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">Attendance Count</th><td>{{ $device->attendance_count !== null ? number_format($device->attendance_count) : '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">Last Connected</th>
                        <td>{{ $device->last_connected_at ? $device->last_connected_at->timezone(config('app.timezone'))->format('M d, Y H:i:s') : '—' }}</td></tr>
                    <tr><th class="text-muted fw-normal">Last Sync</th>
                        <td>{{ $device->last_sync_at ? \Carbon\Carbon::parse($device->last_sync_at)->timezone(config('app.timezone'))->format('M d, Y H:i:s') : '—' }}</td></tr>
                </table>
                <div class="mt-2">
                    <span class="badge bg-success-subtle text-success border border-success-subtle">
                        <i class="bi bi-shield-check me-1"></i>READ ONLY — No write operations to device
                    </span>
                </div>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card border-0 shadow-sm">
            <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">Sync History</div>
            <div class="card-body pt-0">
                @if($syncHistory->isEmpty())
                    <p class="text-muted small">No sync history yet.</p>
                @else
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead class="table-light"><tr>
                            <th>Date</th><th>Status</th><th>Read</th><th>New</th><th>Duration</th>
                        </tr></thead>
                        <tbody>
                        @foreach($syncHistory as $run)
                        <tr>
                            <td class="small">{{ $run->started_at ? $run->started_at->timezone(config('app.timezone'))->format('M d H:i') : '—' }}</td>
                            <td><span class="badge bg-{{ $run->status_badge }}">{{ $run->status }}</span></td>
                            <td>{{ number_format($run->records_read) }}</td>
                            <td>{{ number_format($run->records_inserted) }}</td>
                            <td class="small">{{ $run->duration_formatted }}</td>
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
