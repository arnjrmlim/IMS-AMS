<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login — {{ config('app.name') }}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <style>
        body { background: #1e2a3a; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-card { width: 100%; max-width: 400px; }
        .login-brand { color: #fff; font-weight: 700; font-size: 1.1rem; line-height: 1.3; }
    </style>
</head>
<body>
<div class="login-card">
    <div class="text-center mb-4">
        <div class="login-brand">
            <i class="bi bi-building fs-1 text-primary"></i><br>
            Head Office<br>
            <span class="fw-normal opacity-75 fs-6">Attendance System</span>
        </div>
    </div>

    <div class="card shadow-lg border-0">
        <div class="card-body p-4">
            <h5 class="card-title mb-4 text-center fw-semibold">Sign In</h5>

            @if($errors->any())
                <div class="alert alert-danger py-2 small">
                    @foreach($errors->all() as $error)
                        <div><i class="bi bi-exclamation-circle me-1"></i>{{ $error }}</div>
                    @endforeach
                </div>
            @endif

            <form method="POST" action="{{ route('login.post') }}">
                @csrf

                <div class="mb-3">
                    <label for="username" class="form-label fw-semibold">Username</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="bi bi-person"></i></span>
                        <input
                            type="text"
                            id="username"
                            name="username"
                            class="form-control @error('username') is-invalid @enderror"
                            value="{{ old('username') }}"
                            autocomplete="username"
                            autofocus
                            required
                        >
                    </div>
                </div>

                <div class="mb-4">
                    <label for="password" class="form-label fw-semibold">Password</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="bi bi-lock"></i></span>
                        <input
                            type="password"
                            id="password"
                            name="password"
                            class="form-control"
                            autocomplete="current-password"
                            required
                        >
                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div class="form-check">
                        <input type="checkbox" id="remember" name="remember" class="form-check-input">
                        <label for="remember" class="form-check-label small">Remember me</label>
                    </div>
                </div>

                <button type="submit" class="btn btn-primary w-100">
                    <i class="bi bi-box-arrow-in-right me-1"></i> Sign In
                </button>
            </form>
        </div>
    </div>

    <p class="text-center text-white-50 small mt-3">
        {{ config('app.name') }} &mdash; Phase 4
    </p>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
