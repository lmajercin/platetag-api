<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Mailgun, Postmark, AWS and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'key' => env('POSTMARK_API_KEY'),
    ],

    'resend' => [
        'key' => env('RESEND_API_KEY'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    // Social login — Google OAuth client IDs.
    // All three are checked as valid audiences when verifying Google ID tokens.
    // GOOGLE_CLIENT_ID  = Web / server client ID (used as webClientId in the app)
    // GOOGLE_IOS_CLIENT_ID    = iOS OAuth client
    // GOOGLE_ANDROID_CLIENT_ID = Android OAuth client
    'google' => [
        'client_id'         => env('GOOGLE_CLIENT_ID'),
        'ios_client_id'     => env('GOOGLE_IOS_CLIENT_ID'),
        'android_client_id' => env('GOOGLE_ANDROID_CLIENT_ID'),
    ],

    // Social login — Facebook
    // FACEBOOK_APP_ID + FACEBOOK_APP_SECRET from the Facebook Developer Console.
    'facebook' => [
        'client_id'     => env('FACEBOOK_APP_ID'),
        'client_secret' => env('FACEBOOK_APP_SECRET'),
    ],

    // RevenueCat — purchase verification (V2 API).
    // secret_key: V2 secret key from RevenueCat dashboard (Settings → API Keys → Secret keys).
    // project_id: found in RevenueCat → Project Settings (e.g. proj206dfbae). Required for V2 API.
    // NEVER use the public/app SDK key here — that belongs in the mobile app only.
    // entitlement_id: the entitlement identifier configured in RevenueCat dashboard.
    'revenuecat' => [
        'secret_key'     => env('REVENUECAT_SECRET_KEY'),
        'project_id'     => env('REVENUECAT_PROJECT_ID'),
        'entitlement_id' => env('REVENUECAT_ENTITLEMENT_ID', 'full_access'),
        // Comma-separated list of valid product IDs. Any product_id not in this list is rejected.
        // Must match exactly what is configured in App Store Connect + Google Play.
        'product_ids'    => env('REVENUECAT_PRODUCT_IDS', ''),
    ],

    // Sign in with Apple — server-side JWT verification and token revocation.
    // team_id:    Apple Developer Team ID (top-right on developer.apple.com)
    // key_id:     Key ID from the .p8 key created in Keys section
    // bundle_id:  iOS app bundle identifier — used as both client_id and aud claim
    // private_key_path: absolute path to the downloaded .p8 file (never commit the file or its contents)
    'apple' => [
        'team_id'          => env('APPLE_TEAM_ID'),
        'key_id'           => env('APPLE_KEY_ID'),
        'bundle_id'        => env('APPLE_BUNDLE_ID', 'app.platetag.mobile'),
        'private_key_path' => env('APPLE_PRIVATE_KEY_PATH'),
    ],

    // OpenAI — used by the local plate tagger (tagger:run artisan command).
    // NEVER commit the actual key. Local WAMP only — not needed on production.
    'openai' => [
        'key' => env('OPENAI_API_KEY'),
    ],

    // Google Play Integrity API — server-side verdict verification.
    // credentials_json: base64-encoded Google service account JSON scoped to playintegrity.googleapis.com.
    // package: Android package name of the app (must match what was registered in Play Console).
    'play_integrity' => [
        'credentials_json' => env('GOOGLE_PLAY_INTEGRITY_CREDENTIALS_JSON'),
        'package'          => env('GOOGLE_PLAY_INTEGRITY_PACKAGE', 'app.platetag.mobile'),
    ],

];
