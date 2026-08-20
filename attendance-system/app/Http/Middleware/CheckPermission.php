<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Checks that the authenticated user has the required permission slug.
 * Usage in routes: ->middleware('permission:view_attendance')
 */
class CheckPermission
{
    public function handle(Request $request, Closure $next, string $permission): Response
    {
        if (! $request->user()?->hasPermission($permission)) {
            if ($request->expectsJson()) {
                return response()->json(['message' => 'Forbidden.'], 403);
            }
            abort(403);
        }

        return $next($request);
    }
}
