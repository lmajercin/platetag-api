<?php

return [
    'paths' => [
        'api/*',
        'sanctum/csrf-cookie',
    ],

    'allowed_methods' => ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],

    'allowed_origins' => [
        'https://platetag.app',
        'https://www.platetag.app',
        'https://platetag-web.vercel.app',
        'http://localhost:3000',
        'http://localhost:3001',
        'http://localhost:19006',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:19006',
    ],

    'allowed_origins_patterns' => [
        '#^https://[a-z0-9\-]+-lm-ajercin-s-projects\.vercel\.app$#',
        '#^https://platetag-web[a-z0-9\-]*\.vercel\.app$#',
    ],

    'allowed_headers' => [
        'Content-Type',
        'X-Requested-With',
        'Authorization',
        'Accept',
        'Origin',
        'X-XSRF-TOKEN',
    ],

    'exposed_headers' => [],

    'max_age' => 3600,

    'supports_credentials' => true,
];