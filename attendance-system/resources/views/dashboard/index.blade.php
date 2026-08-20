@extends('layouts.app')
@section('title', 'Dashboard')

@section('content')

{{-- Integration status banner --}}
@if(! ($health['online'] ?? false))
<div class="api-offline-banner mb-3 d-flex align-items-center gap-2">
    <i class="bi bi-exclamation-triangle-fill text-warning"></i>
    <span>
        <strong>Integration service is offline.</strong>
        Attendance data may be outdated.
        Start it: <code>python run.py serve</code> in the <code>speedface-integration</code> directory.
    </span>
</div>
@endif

{{-- Stat cards --}}
<div class="row g-3 mb-4">
    <div class="col-6 col-md-3">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
                <div class="d-flex align-items-center gap-3">
                    <div class="rounded-3 p-2 bg-primary bg-opacity-10">
                        <i class="bi bi-cpu fs-4 text-primary"></i>
                    </div>
                    <div>
                        <div class="fs-4 fw-bold">{{ $stats['devices'] }}</div>
                        <div class="text-muted small">Devices</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="col-6 col-md-3">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
                <div class="d-flex align-items-center gap-3">
                    <div class="rounded-3 p-2 bg-success bg-opacity-10">
                        <i class="bi bi-wifi fs-4 text-success"></i>
                    </div>
                    <div>
                        <div class="fs-4 fw-bold">{{ $stats['online_devices'] }}</div>
                        <div class="text-muted small">Online</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="col-6 col-md-3">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
                <div class="d-flex align-items-center gap-3">
                    <div class="rounded-3 p-2 bg-info bg-opacity-10">
                        <i class="bi bi-people fs-4 text-info"></i>
                    </div>
                    <div>
                        <div class="fs-4 fw-bold">{{ $stats['employees'] }}</div>
                        <div class="text-muted small">Employees</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="col-6 col-md-3">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
                <div class="d-flex align-items-center gap-3">
                    <div class="rounded-3 p-2 bg-warning bg-opacity-10">
                        <i class="bi bi-clock-history fs-4 text-warning"></i>
                    </div>
                    <div>
                        <div class="fs-4 fw-bold">{{ number_format($stats['attendance_records']) }}</div>
                        <div class="text-muted small">Attendance Records</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row g-3">
    {{-- Sync Status --}}
    <div class="col-md-6">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">
                <i class="bi bi-arrow-repeat text-primary me-1"></i> Synchronisation Status
            </div>
            <div class="card-body">
                @if($health['online'] ?? false)
                    @php
                        $status     = $syncData['last_sync_status'] ?? null;
                        $lastSync   = $syncData['last_sync_at'] ?? null;
                        $recCount   = $syncData['local_record_count'] ?? 0;
                        $lastRecord = $syncData['last_record_datetime'] ?? null;
                        $inProgress = $syncData['sync_in_progress'] ?? false;
                    @endphp

                    @if($inProgress)
                        <span class="badge bg-info mb-2"><i class="bi bi-arrow-repeat spin me-1"></i>RUNNING</span>
                    @elseif($status === 'success')
                        <span class="badge bg-success mb-2"><i class="bi bi-check-circle me-1"></i>SUCCESS</span>
                    @elseif($status === 'failed')
                        <span class="badge bg-danger mb-2"><i class="bi bi-x-circle me-1"></i>FAILED</span>
                    @elseif($status)
                        <span class="badge bg-warning text-dark mb-2">{{ strtoupper($status) }}</span>
                    @else
                        <span class="badge bg-secondary mb-2">NO SYNC YET</span>
                    @endif

                    <table class="table table-sm table-borderless mb-0 mt-2">
                        <tr>
                            <td class="text-muted" style="width:40%">Last Sync</td>
                            <td class="fw-semibold">{{ $lastSync ? \Carbon\Carbon::parse($lastSync)->timezone(config('app.timezone'))->format('M d, Y H:i') : '—' }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Python Records</td>
                            <td class="fw-semibold">{{ number_format($recCount) }}</td>
                        </tr>
                        <tr>
                            <td class="text-muted">Last Record</td>
                            <td class="fw-semibold">{{ $lastRecord ? \Carbon\Carbon::parse($lastRecord)->timezone(config('app.timezone'))->format('M d, Y H:i') : '—' }}</td>
                        </tr>
                    </table>

                    @can('run_sync')
                    <div class="mt-3">
                        <a href="{{ route('sync.index') }}" class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-arrow-repeat me-1"></i> Go to Sync
                        </a>
                    </div>
                    @endcan
                @else
                    <p class="text-muted mb-0"><i class="bi bi-plug-fill me-1 text-danger"></i>Integration service offline.</p>
                @endif
            </div>
        </div>
    </div>

    {{-- Integration Service Status --}}
    <div class="col-md-6">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">
                <i class="bi bi-cpu text-primary me-1"></i> SpeedFace Integration
            </div>
            <div class="card-body">
                @if($health['online'] ?? false)
                    <div class="d-flex align-items-center gap-2 mb-3">
                        <span class="badge bg-success rounded-pill px-3 py-2">
                            <i class="bi bi-circle-fill me-1" style="font-size:.5rem"></i> Online
                        </span>
                        <span class="text-muted small">Python Integration Service v{{ $health['data']['version'] ?? '?' }}</span>
                    </div>
                @else
                    <div class="d-flex align-items-center gap-2 mb-3">
                        <span class="badge bg-danger rounded-pill px-3 py-2">
                            <i class="bi bi-circle-fill me-1" style="font-size:.5rem"></i> Offline
                        </span>
                        <span class="text-muted small">Cannot reach integration service</span>
                    </div>
                @endif

                @if($lastSync ?? null)
                <table class="table table-sm table-borderless mb-0">
                    <tr>
                        <td class="text-muted" style="width:45%">API URL</td>
                        <td class="fw-semibold text-break" style="font-size:.8rem">{{ config('services.speedface.url') }}</td>
                    </tr>
                    <tr>
                        <td class="text-muted">Device Policy</td>
                        <td><span class="badge bg-success-subtle text-success border border-success-subtle">READ ONLY</span></td>
                    </tr>
                </table>
                @endif

                @can('view_devices')
                <div class="mt-3">
                    <a href="{{ route('devices.index') }}" class="btn btn-sm btn-outline-secondary">
                        <i class="bi bi-cpu me-1"></i> View Devices
                    </a>
                </div>
                @endcan
            </div>
        </div>
    </div>
</div>

@endsection

@push('styles')
<style>
    @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
    .spin { display:inline-block; animation: spin 1.5s linear infinite; }
</style>
@endpush
