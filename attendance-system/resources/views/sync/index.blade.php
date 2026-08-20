@extends('layouts.app')
@section('title', 'Synchronisation')

@section('content')

@if(! $apiOnline)
<div class="api-offline-banner mb-3">
    <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
    <strong>Integration service is offline.</strong>
    Unable to retrieve synchronisation status.
    Run <code>python run.py serve</code> in the <code>speedface-integration</code> directory.
</div>
@endif

<div class="d-flex align-items-center justify-content-between mb-3">
    <h4 class="mb-0 fw-semibold"><i class="bi bi-arrow-repeat me-2 text-primary"></i>Synchronisation</h4>
    @can('run_sync')
    <button id="sync-btn" class="btn btn-primary">
        <i class="bi bi-arrow-repeat me-1"></i> Sync Now
    </button>
    @endcan
</div>

{{-- Sync result toast --}}
<div id="sync-result" class="d-none alert mb-3"></div>

<div class="row g-3 mb-4">
    {{-- Current Status --}}
    <div class="col-md-6">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">Current Status</div>
            <div class="card-body pt-0">
                @if($syncStatus)
                    @php
                        $status     = $syncStatus['last_sync_status'] ?? null;
                        $inProgress = $syncStatus['sync_in_progress']  ?? false;
                        $lastSync   = $syncStatus['last_sync_at'] ?? null;
                        $recCount   = $syncStatus['local_record_count'] ?? 0;
                        $lastRecord = $syncStatus['last_record_datetime'] ?? null;
                        $totalRuns  = $syncStatus['total_sync_runs'] ?? 0;
                        $lastRun    = $syncStatus['last_run'] ?? null;
                    @endphp

                    <div class="mb-3">
                        @if($inProgress)
                            <span class="badge bg-info fs-6 py-2 px-3">
                                <span class="spinner-border spinner-border-sm me-1"></span> RUNNING
                            </span>
                        @elseif($status === 'success')
                            <span class="badge bg-success fs-6 py-2 px-3"><i class="bi bi-check-circle me-1"></i>SUCCESS</span>
                        @elseif($status === 'failed')
                            <span class="badge bg-danger fs-6 py-2 px-3"><i class="bi bi-x-circle me-1"></i>FAILED</span>
                        @elseif($status === 'partial')
                            <span class="badge bg-warning text-dark fs-6 py-2 px-3">PARTIAL</span>
                        @else
                            <span class="badge bg-secondary fs-6 py-2 px-3">NO SYNC YET</span>
                        @endif
                    </div>

                    <table class="table table-sm">
                        <tr><td class="text-muted">Last Sync</td>
                            <td>{{ $lastSync ? \Carbon\Carbon::parse($lastSync)->timezone(config('app.timezone'))->format('M d, Y H:i:s') : '—' }}</td></tr>
                        <tr><td class="text-muted">Python Records Stored</td>
                            <td>{{ number_format($recCount) }}</td></tr>
                        <tr><td class="text-muted">Last Record Datetime</td>
                            <td>{{ $lastRecord ? \Carbon\Carbon::parse($lastRecord)->timezone(config('app.timezone'))->format('M d, Y H:i:s') : '—' }}</td></tr>
                        <tr><td class="text-muted">Total Sync Runs</td>
                            <td>{{ $totalRuns }}</td></tr>
                        @if($lastRun)
                        <tr><td class="text-muted">Last Run Read</td><td>{{ number_format($lastRun['records_read'] ?? 0) }}</td></tr>
                        <tr><td class="text-muted">Last Run Inserted</td><td>{{ number_format($lastRun['records_inserted'] ?? 0) }}</td></tr>
                        <tr><td class="text-muted">Last Run Skipped</td><td>{{ number_format($lastRun['records_skipped'] ?? 0) }}</td></tr>
                        @endif
                    </table>
                @else
                    <p class="text-muted">Status unavailable — integration service offline.</p>
                @endif
            </div>
        </div>
    </div>

    {{-- Device Safety --}}
    <div class="col-md-6">
        <div class="card border-0 shadow-sm h-100">
            <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">Device Safety</div>
            <div class="card-body pt-0">
                <div class="alert alert-success border-0 py-2 mb-3">
                    <i class="bi bi-shield-check me-1"></i>
                    <strong>READ ONLY</strong> — The SpeedFace-V5L is never modified by this system.
                </div>
                <p class="small text-muted mb-2">The synchronisation service:</p>
                <ul class="small text-muted ps-3">
                    <li>Reads attendance records from the device</li>
                    <li>Stores a local copy in the Python SQLite database</li>
                    <li>This page then reads from the Python API</li>
                    <li>No attendance records are deleted from the device</li>
                    <li>No users are modified on the device</li>
                </ul>
                <p class="small text-muted">
                    <strong>Flow:</strong> SpeedFace → Python Service → SQLite → Python API → Laravel → MySQL
                </p>
            </div>
        </div>
    </div>
</div>

{{-- Local sync history --}}
<div class="card border-0 shadow-sm">
    <div class="card-header bg-white fw-semibold border-bottom-0 pt-3">Local Sync History</div>
    <div class="card-body p-0">
        @if($localRuns->isEmpty())
            <div class="p-4 text-muted text-center">No sync runs recorded yet.</div>
        @else
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead class="table-light">
                    <tr>
                        <th>#</th><th>Date</th><th>Status</th>
                        <th>Read</th><th>Inserted</th><th>Skipped</th><th>Failed</th>
                        <th>Duration</th><th>By</th>
                    </tr>
                </thead>
                <tbody>
                @foreach($localRuns as $run)
                <tr>
                    <td class="text-muted small">{{ $run->id }}</td>
                    <td class="small">{{ $run->started_at ? $run->started_at->timezone(config('app.timezone'))->format('M d, Y H:i') : '—' }}</td>
                    <td><span class="badge bg-{{ $run->status_badge }}">{{ $run->status }}</span></td>
                    <td>{{ number_format($run->records_read) }}</td>
                    <td class="text-success">{{ number_format($run->records_inserted) }}</td>
                    <td class="text-muted">{{ number_format($run->records_skipped) }}</td>
                    <td class="{{ $run->records_failed > 0 ? 'text-danger' : 'text-muted' }}">{{ number_format($run->records_failed) }}</td>
                    <td class="small">{{ $run->duration_formatted }}</td>
                    <td class="small text-muted">{{ $run->triggeredBy?->name ?? 'System' }}</td>
                </tr>
                @endforeach
                </tbody>
            </table>
        </div>
        <div class="p-3">{{ $localRuns->links() }}</div>
        @endif
    </div>
</div>

@endsection

@push('scripts')
<script>
const syncBtn    = document.getElementById('sync-btn');
const resultBox  = document.getElementById('sync-result');
const statusUrl  = '{{ route('sync.status') }}';
const triggerUrl = '{{ route('sync.trigger') }}';
const csrfToken  = document.querySelector('meta[name=csrf-token]').content;

if (syncBtn) {
    syncBtn.addEventListener('click', function () {
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Synchronising...';
        resultBox.className = 'd-none';

        fetch(triggerUrl, {
            method: 'POST',
            headers: { 'X-CSRF-TOKEN': csrfToken, 'Accept': 'application/json', 'Content-Type': 'application/json' }
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showResult('info', data.message);
                // Poll for completion
                pollStatus();
            } else if (data.code === 'SYNC_IN_PROGRESS') {
                showResult('warning', data.message);
                resetBtn();
            } else {
                showResult('danger', data.message || 'Sync trigger failed.');
                resetBtn();
            }
        })
        .catch(() => { showResult('danger', 'Could not contact the server.'); resetBtn(); });
    });
}

function pollStatus() {
    let attempts = 0;
    const interval = setInterval(() => {
        attempts++;
        fetch(statusUrl, { headers: { 'Accept': 'application/json' } })
        .then(r => r.json())
        .then(data => {
            if (! data.ok) { clearInterval(interval); resetBtn(); return; }
            const inProgress = data.data?.sync_in_progress;
            if (! inProgress || attempts >= 60) {
                clearInterval(interval);
                const status = data.data?.last_sync_status;
                if (status === 'success') {
                    showResult('success', 'Synchronisation completed successfully. Refreshing…');
                    setTimeout(() => location.reload(), 2000);
                } else if (status === 'failed') {
                    showResult('danger', 'Synchronisation failed. Check the integration service logs.');
                    resetBtn();
                } else {
                    location.reload();
                }
            }
        })
        .catch(() => { clearInterval(interval); resetBtn(); });
    }, 3000);
}

function showResult(type, msg) {
    resultBox.className = `alert alert-${type}`;
    resultBox.innerHTML = `<i class="bi bi-info-circle me-1"></i>${msg}`;
}

function resetBtn() {
    if (syncBtn) {
        syncBtn.disabled = false;
        syncBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Sync Now';
    }
}
</script>
@endpush
