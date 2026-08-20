<?php

return [

    'postmark' => ['key' => env('POSTMARK_API_KEY')],
    'resend'   => ['key' => env('RESEND_API_KEY')],
    'ses'      => [
        'key'    => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],
    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel'              => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    // ── Phase 3 Python Integration Service ────────────────────────────────
    // Browser → Laravel → here → Python API  (key never sent to browser)
    'speedface' => [
        'url'     => env('SPEEDFACE_API_URL',     'http://127.0.0.1:8000/api'),
        'key'     => env('SPEEDFACE_API_KEY',     ''),
        'timeout' => env('SPEEDFACE_API_TIMEOUT', 30),
    ],

];
