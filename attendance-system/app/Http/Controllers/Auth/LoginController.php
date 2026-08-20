<?php

declare(strict_types=1);

namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use App\Models\AuditLog;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Log;
use Illuminate\View\View;

class LoginController extends Controller
{
    public function showLoginForm(): View
    {
        return view('auth.login');
    }

    public function login(Request $request): RedirectResponse
    {
        $credentials = $request->validate([
            'username' => ['required', 'string'],
            'password' => ['required', 'string'],
        ]);

        // Rate limiting: 6 attempts per minute per IP
        $key = 'login_attempts_'.$request->ip();
        if (cache()->get($key, 0) >= 6) {
            return back()
                ->withInput($request->only('username'))
                ->withErrors(['username' => 'Too many login attempts. Please try again in a minute.']);
        }

        if (Auth::attempt(['username' => $credentials['username'], 'password' => $credentials['password']], $request->boolean('remember'))) {
            $request->session()->regenerate();
            cache()->forget($key);

            // Update last login timestamp
            $user = Auth::user();
            $user->update(['last_login_at' => now()]);

            // Audit log
            AuditLog::create([
                'user_id'     => $user->id,
                'action'      => 'login',
                'module'      => 'auth',
                'description' => "User '{$user->username}' logged in.",
                'ip_address'  => $request->ip(),
                'user_agent'  => $request->userAgent(),
            ]);

            Log::info('User login', ['username' => $user->username, 'ip' => $request->ip()]);

            return redirect()->intended(route('dashboard'));
        }

        // Increment failed attempt counter
        cache()->put($key, cache()->get($key, 0) + 1, 60);

        Log::warning('Failed login attempt', ['username' => $credentials['username'], 'ip' => $request->ip()]);

        return redirect()->route('login')
            ->withInput($request->only('username'))
            ->withErrors(['username' => 'These credentials do not match our records.']);
    }

    public function logout(Request $request): RedirectResponse
    {
        $user = Auth::user();

        if ($user) {
            AuditLog::create([
                'user_id'     => $user->id,
                'action'      => 'logout',
                'module'      => 'auth',
                'description' => "User '{$user->username}' logged out.",
                'ip_address'  => $request->ip(),
                'user_agent'  => $request->userAgent(),
            ]);
        }

        Auth::logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return redirect()->route('login');
    }
}
