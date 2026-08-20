<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@yield('code') — {{ config('app.name') }}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <style>
        body { background:#f4f6f9; min-height:100vh; display:flex; align-items:center; justify-content:center; }
        .error-code { font-size:6rem; font-weight:700; line-height:1; color:#dee2e6; }
    </style>
</head>
<body>
<div class="text-center" style="max-width:480px; padding:2rem">
    <div class="error-code">@yield('code')</div>
    <h4 class="fw-semibold mt-2">@yield('title')</h4>
    <p class="text-muted">@yield('message')</p>
    <a href="{{ url('/dashboard') }}" class="btn btn-primary mt-2">
        <i class="bi bi-house me-1"></i>Back to Dashboard
    </a>
</div>
</body>
</html>
