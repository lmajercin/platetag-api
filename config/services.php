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

    // RevenueCat — purchase verification.
    // secret_key: server-to-server key from RevenueCat dashboard (Settings → API Keys → Secret keys).
    // NEVER use the public/app key here — that belongs in the mobile app only.
    // entitlement_id: the entitlement identifier configured in RevenueCat dashboard.
    'revenuecat' => [
        'secret_key'     => env('REVENUECAT_SECRET_KEY'),
        'entitlement_id' => env('REVENUECAT_ENTITLEMENT_ID', 'full_access'),
        // Comma-separated list of valid product IDs. Any product_id not in this list is rejected.
        // Must match exactly what is configured in App Store Connect + Google Play.
        'product_ids'    => env('REVENUECAT_PRODUCT_IDS', ''),
    ],

    // Google Play Integrity API — server-side verdict verification.
    // credentials_json: base64-encoded Google service account JSON scoped to playintegrity.googleapis.com.
    // package: Android package name of the app (must match what was registered in Play Console).
    'play_integrity' => [
        'credentials_json' => env('GOOGLE_PLAY_INTEGRITY_CREDENTIALS_JSON'),
        'package'          => env('GOOGLE_PLAY_INTEGRITY_PACKAGE', 'app.platetag.mobile'),
    ],

];
