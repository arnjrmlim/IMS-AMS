@extends('layouts.app')
@section('title', 'Edit Device User ' . $deviceUser->device_user_id)

@section('content')

<div class="d-flex align-items-center gap-2 mb-3">
    <a href="{{ route('device-users.show', $deviceUser) }}" class="btn btn-sm btn-outline-secondary">
        <i class="bi bi-arrow-left"></i>
    </a>
    <h4 class="mb-0 fw-semibold">
        <i class="bi bi-pencil me-1 text-primary"></i>
        Edit Device User <code>{{ $deviceUser->device_user_id }}</code>
    </h4>
</div>

{{-- READ-ONLY notice --}}
<div class="alert alert-success border-0 py-2 mb-4 small">
    <i class="bi bi-shield-check me-1"></i>
    <strong>READ ONLY DEVICE</strong> — Changes made here are saved to the
    <strong>application database only</strong>. The SpeedFace-V5L will not be modified.
</div>

<form method="POST"
      action="{{ route('device-users.update', $deviceUser) }}"
      id="edit-device-user-form"
      novalidate>
    @csrf
    @method('PUT')

    <div class="row g-3">

        {{-- ── Device Information (read-only) ───────────────────────────── --}}
        <div class="col-12">
            <div class="card border-0 shadow-sm">
                <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">
                    <i class="bi bi-cpu me-1 text-secondary"></i> Device Information
                    <span class="badge bg-secondary ms-2 fw-normal" style="font-size:.7rem">Read-Only</span>
                </div>
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="form-label small text-muted mb-1">Device User ID</label>
                            <div class="form-control form-control-sm bg-light text-muted">
                                {{ $deviceUser->device_user_id }}
                            </div>
                            <div class="form-text">Cannot be changed — assigned by the device.</div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label small text-muted mb-1">Device</label>
                            <div class="form-control form-control-sm bg-light text-muted">
                                {{ $deviceUser->device?->name ?? '—' }}
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small text-muted mb-1">Source Name (from device)</label>
                            <div class="form-control form-control-sm bg-light text-muted">
                                {{ $deviceUser->device_name ?? '—' }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {{-- ── Employee Assignment ────────────────────────────────────────── --}}
        <div class="col-12">
            <div class="card border-0 shadow-sm">
                <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">
                    <i class="bi bi-person-check me-1 text-secondary"></i> Employee Assignment
                </div>
                <div class="card-body">

                    {{-- Hidden employee_id field, populated by JS search --}}
                    <input type="hidden" name="employee_id" id="employee_id"
                           value="{{ old('employee_id', $deviceUser->employee_id) }}">

                    <div class="row g-3">
                        <div class="col-md-6">
                            <label for="employee_search" class="form-label small mb-1">
                                Employee <span class="text-muted fw-normal">(search by name or employee number)</span>
                            </label>
                            <div class="position-relative">
                                <input type="text"
                                       id="employee_search"
                                       class="form-control form-control-sm @error('employee_id') is-invalid @enderror"
                                       placeholder="Type to search employees…"
                                       autocomplete="off"
                                       value="{{ old('employee_id')
                                           ? (App\Models\Employee::find(old('employee_id'))?->full_name ?? '')
                                           : ($deviceUser->employee?->full_name ?? '') }}">
                                {{-- Dropdown results --}}
                                <ul id="employee_results"
                                    class="list-group position-absolute w-100 shadow-sm d-none"
                                    style="z-index:1050; max-height:220px; overflow-y:auto; top:100%">
                                </ul>
                            </div>
                            @error('employee_id')
                                <div class="invalid-feedback d-block">{{ $message }}</div>
                            @enderror
                            {{-- Selected badge --}}
                            <div id="employee_selected" class="mt-1">
                                @if($deviceUser->employee)
                                    <span class="badge bg-success">
                                        <i class="bi bi-check-circle me-1"></i>
                                        {{ $deviceUser->employee->full_name }}
                                        ({{ $deviceUser->employee->employee_number }})
                                    </span>
                                @endif
                            </div>
                        </div>

                        <div class="col-md-3 d-flex align-items-end">
                            @if($deviceUser->employee_id)
                            <button type="button"
                                    id="clear_employee"
                                    class="btn btn-sm btn-outline-danger">
                                <i class="bi bi-person-x me-1"></i>Remove Assignment
                            </button>
                            @endif
                        </div>
                    </div>

                    {{-- Confirmation notice for mapping change --}}
                    <div id="mapping_notice" class="alert alert-warning border-0 py-2 mt-3 small d-none">
                        <i class="bi bi-exclamation-triangle me-1"></i>
                        <strong>Confirm Assignment:</strong>
                        You are changing the employee associated with Device User ID
                        <strong>{{ $deviceUser->device_user_id }}</strong>.
                        This change affects the <strong>application database only</strong>.
                        The SpeedFace device will not be modified.
                    </div>

                </div>
            </div>
        </div>

        {{-- ── Employee Information ───────────────────────────────────────── --}}
        <div class="col-12" id="employee_info_section"
             style="{{ ($deviceUser->employee_id || old('employee_id')) ? '' : 'display:none' }}">
            <div class="card border-0 shadow-sm">
                <div class="card-header bg-white fw-semibold pt-3 border-bottom-0">
                    <i class="bi bi-person me-1 text-secondary"></i> Employee Information
                    <span class="text-muted fw-normal small ms-1">(application database)</span>
                </div>
                <div class="card-body">
                    <div class="row g-3">

                        <div class="col-md-3">
                            <label for="first_name" class="form-label small mb-1">
                                First Name <span class="text-danger">*</span>
                            </label>
                            <input type="text" id="first_name" name="first_name"
                                   class="form-control form-control-sm @error('first_name') is-invalid @enderror"
                                   value="{{ old('first_name', $deviceUser->employee?->first_name) }}"
                                   maxlength="80">
                            @error('first_name')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-3">
                            <label for="middle_name" class="form-label small mb-1">Middle Name</label>
                            <input type="text" id="middle_name" name="middle_name"
                                   class="form-control form-control-sm @error('middle_name') is-invalid @enderror"
                                   value="{{ old('middle_name', $deviceUser->employee?->middle_name) }}"
                                   maxlength="80">
                            @error('middle_name')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-3">
                            <label for="last_name" class="form-label small mb-1">
                                Last Name <span class="text-danger">*</span>
                            </label>
                            <input type="text" id="last_name" name="last_name"
                                   class="form-control form-control-sm @error('last_name') is-invalid @enderror"
                                   value="{{ old('last_name', $deviceUser->employee?->last_name) }}"
                                   maxlength="80">
                            @error('last_name')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-2">
                            <label for="suffix" class="form-label small mb-1">Suffix</label>
                            <input type="text" id="suffix" name="suffix"
                                   class="form-control form-control-sm @error('suffix') is-invalid @enderror"
                                   value="{{ old('suffix', $deviceUser->employee?->suffix) }}"
                                   placeholder="Jr., Sr., III…" maxlength="10">
                            @error('suffix')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-2">
                            <label for="employee_number" class="form-label small mb-1">
                                Employee No. <span class="text-danger">*</span>
                            </label>
                            <input type="text" id="employee_number" name="employee_number"
                                   class="form-control form-control-sm @error('employee_number') is-invalid @enderror"
                                   value="{{ old('employee_number', $deviceUser->employee?->employee_number) }}"
                                   maxlength="30">
                            @error('employee_number')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-3">
                            <label for="branch_id" class="form-label small mb-1">Branch</label>
                            <select id="branch_id" name="branch_id"
                                    class="form-select form-select-sm @error('branch_id') is-invalid @enderror">
                                <option value="">— No Branch —</option>
                                @foreach($branches as $branch)
                                    <option value="{{ $branch->id }}"
                                        {{ old('branch_id', $deviceUser->employee?->branch_id) == $branch->id ? 'selected' : '' }}>
                                        {{ $branch->name }}
                                    </option>
                                @endforeach
                            </select>
                            @error('branch_id')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-3">
                            <label for="department_id" class="form-label small mb-1">Department</label>
                            <select id="department_id" name="department_id"
                                    class="form-select form-select-sm @error('department_id') is-invalid @enderror">
                                <option value="">— No Department —</option>
                                @foreach($departments as $dept)
                                    <option value="{{ $dept->id }}"
                                        {{ old('department_id', $deviceUser->employee?->department_id) == $dept->id ? 'selected' : '' }}>
                                        {{ $dept->name }}
                                    </option>
                                @endforeach
                            </select>
                            @error('department_id')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="col-md-2">
                            <label for="status" class="form-label small mb-1">
                                Status <span class="text-danger">*</span>
                            </label>
                            <select id="status" name="status"
                                    class="form-select form-select-sm @error('status') is-invalid @enderror">
                                <option value="active"   {{ old('status', $deviceUser->employee?->status) === 'active'   ? 'selected' : '' }}>Active</option>
                                <option value="inactive" {{ old('status', $deviceUser->employee?->status) === 'inactive' ? 'selected' : '' }}>Inactive</option>
                                <option value="resigned" {{ old('status', $deviceUser->employee?->status) === 'resigned' ? 'selected' : '' }}>Resigned</option>
                            </select>
                            @error('status')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                    </div>
                </div>
            </div>
        </div>

        {{-- ── Form Actions ───────────────────────────────────────────────── --}}
        <div class="col-12 d-flex gap-2 justify-content-end">
            <a href="{{ route('device-users.show', $deviceUser) }}"
               class="btn btn-outline-secondary">
                <i class="bi bi-x me-1"></i>Cancel
            </a>
            <button type="submit" class="btn btn-primary">
                <i class="bi bi-check-lg me-1"></i>Save Changes
            </button>
        </div>

    </div>
</form>

@endsection

@push('scripts')
<script>
const searchInput    = document.getElementById('employee_search');
const resultsBox     = document.getElementById('employee_results');
const employeeIdField = document.getElementById('employee_id');
const selectedBadge  = document.getElementById('employee_selected');
const infoSection    = document.getElementById('employee_info_section');
const clearBtn       = document.getElementById('clear_employee');
const mappingNotice  = document.getElementById('mapping_notice');
const searchUrl      = '{{ route('device-users.employee-search') }}';
const originalEmpId  = '{{ $deviceUser->employee_id }}';

let debounceTimer = null;

// ── Live employee search ────────────────────────────────────────────────────
searchInput?.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    const term = this.value.trim();

    if (term.length < 2) {
        hideResults();
        return;
    }

    debounceTimer = setTimeout(() => {
        fetch(`${searchUrl}?q=${encodeURIComponent(term)}`, {
            headers: { 'Accept': 'application/json' }
        })
        .then(r => r.json())
        .then(data => {
            renderResults(data);
        })
        .catch(() => hideResults());
    }, 250);
});

function renderResults(employees) {
    resultsBox.innerHTML = '';

    if (employees.length === 0) {
        resultsBox.innerHTML = '<li class="list-group-item list-group-item-action text-muted small disabled">No employees found.</li>';
        resultsBox.classList.remove('d-none');
        return;
    }

    employees.forEach(emp => {
        const li = document.createElement('li');
        li.className = 'list-group-item list-group-item-action py-2';
        li.style.cursor = 'pointer';
        li.innerHTML = `
            <span class="fw-semibold">${emp.full_name}</span>
            <span class="text-muted small ms-1">${emp.employee_number}</span>
            ${emp.department ? `<span class="badge bg-light text-dark border ms-1 small">${emp.department}</span>` : ''}
        `;
        li.addEventListener('click', () => selectEmployee(emp));
        resultsBox.appendChild(li);
    });

    resultsBox.classList.remove('d-none');
}

function selectEmployee(emp) {
    employeeIdField.value = emp.id;
    searchInput.value     = emp.full_name;
    hideResults();

    // Update selected badge
    selectedBadge.innerHTML = `
        <span class="badge bg-success mt-1">
            <i class="bi bi-check-circle me-1"></i>
            ${emp.full_name} (${emp.employee_number})
        </span>`;

    // Show employee info section
    infoSection.style.display = '';

    // Show mapping change notice if employee changed
    if (String(emp.id) !== String(originalEmpId)) {
        mappingNotice.classList.remove('d-none');
    } else {
        mappingNotice.classList.add('d-none');
    }

    // Pre-fill name fields from selected employee via another fetch
    fetch(`${searchUrl}?q=${encodeURIComponent(emp.employee_number)}`, {
        headers: { 'Accept': 'application/json' }
    })
    .then(r => r.json())
    .then(data => {
        const found = data.find(e => String(e.id) === String(emp.id));
        if (found) populateEmployeeFields(found);
    });
}

function populateEmployeeFields(emp) {
    // Only pre-fill if fields are currently empty (don't overwrite admin edits)
    const fields = {
        first_name: emp.first_name ?? '',
        middle_name: emp.middle_name ?? '',
        last_name: emp.last_name ?? '',
        suffix: emp.suffix ?? '',
        employee_number: emp.employee_number ?? '',
    };
    Object.entries(fields).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (el && el.value === '') el.value = val;
    });
}

function hideResults() {
    resultsBox.classList.add('d-none');
    resultsBox.innerHTML = '';
}

// Hide results on outside click
document.addEventListener('click', e => {
    if (! searchInput?.contains(e.target) && ! resultsBox?.contains(e.target)) {
        hideResults();
    }
});

// ── Clear assignment ────────────────────────────────────────────────────────
clearBtn?.addEventListener('click', function () {
    employeeIdField.value = '';
    searchInput.value     = '';
    selectedBadge.innerHTML = '';
    infoSection.style.display = 'none';
    mappingNotice.classList.add('d-none');
    hideResults();
});
</script>
@endpush
