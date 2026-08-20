<?php

use App\Http\Middleware\CheckActive;
use App\Http\Middleware\CheckPermission;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web:      __DIR__.'/../routes/web.php',
        commands: __DIR__.'/../routes/console.php',
        health:   '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        // Register named middleware aliases
        $middleware->alias([
            'permission' => CheckPermission::class,
            'active'     => CheckActive::class,
        ]);

        // Apply active-account check to all authenticated web routes
        $middleware->web(append: [
            CheckActive::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        // Render friendly error pages
        $exceptions->render(function (\Illuminate\Auth\AuthenticationException $e, Request $request) {
            if (! $request->expectsJson()) {
                return redirect()->route('login');
            }
        });
    })->create();
