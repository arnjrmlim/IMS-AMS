<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\AuditLog;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Request;

class AuditService
{
    public static function log(
        string $action,
        string $description,
        string $module = 'general',
        array  $context = []
    ): void {
        AuditLog::create([
            'user_id'     => Auth::id(),
            'action'      => $action,
            'module'      => $module,
            'description' => $description,
            'ip_address'  => Request::ip(),
            'user_agent'  => Request::userAgent(),
            'context'     => empty($context) ? null : $context,
        ]);
    }
}
