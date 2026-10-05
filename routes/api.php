<?php

use App\Http\Middleware\CheckPlayIntegrity;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\BrowseController;
use App\Http\Controllers\Api\BugReportController;
use App\Http\Controllers\Api\CollectionController;
use App\Http\Controllers\Api\OfflineController;
use App\Http\Controllers\Api\PlatesController;
use App\Http\Controllers\Api\PlateRequestController;
use App\Http\Controllers\Api\PromoController;
use App\Http\Controllers\Api\PurchaseController;
use App\Http\Controllers\Api\SessionController;
use App\Http\Controllers\Api\SocialAuthController;

Route::prefix('v1')->group(function () {

    // Public auth — tightly rate-limited (10/min per IP)
    Route::middleware('throttle:auth')->prefix('auth')->group(function () {
        Route::post('register',           [AuthController::class, 'register']);
        Route::post('login',              [AuthController::class, 'login']);
        Route::post('forgot-password',    [AuthController::class, 'forgotPassword']);
        Route::post('reset-password',     [AuthController::class, 'resetPassword']);
        Route::post('social/callback',     [SocialAuthController::class, 'callback']);
    });

    // Web social sign-in — establishes a Sanctum cookie session (no token issued).
    // Mobile tokens are never touched by this route.
    Route::middleware(['throttle:auth'])->prefix('auth')->group(function () {
        Route::post('social/web-callback', [SocialAuthController::class, 'webCallback']);
    });

    // Web SPA session auth — cookie-based, no tokens (platetag.app Next.js frontend).
    // Mobile clients use the token-based routes above; these are web-only.
    Route::middleware(['throttle:auth'])->prefix('auth/web')->group(function () {
        Route::post('login',    [AuthController::class, 'webLogin']);
        Route::post('register', [AuthController::class, 'webRegister']);
        Route::post('logout',   [AuthController::class, 'webLogout']);
    });

    // Email verification resend — requires auth
    Route::middleware(['auth:sanctum', 'throttle:submissions'])->group(function () {
        Route::post('auth/email/resend', [AuthController::class, 'resendVerification']);
    });

    // Account management — tightly rate-limited, require auth
    Route::middleware(['auth:sanctum', 'throttle:auth'])->group(function () {
        Route::post('auth/change-password',       [AuthController::class, 'changePassword']);
        Route::delete('auth/account',             [AuthController::class, 'deleteAccount']);
        Route::post('auth/email-change/request',  [AuthController::class, 'requestEmailChange']);
        Route::post('auth/email-change/confirm',  [AuthController::class, 'confirmEmailChange']);
    });

    // Public browse — general rate limit (60/min per IP)
    Route::middleware('throttle:api')->group(function () {
        Route::get('plates',               [PlatesController::class, 'index']);
        Route::get('plates/{id}',          [PlatesController::class, 'show']);
        Route::get('regions',              [BrowseController::class, 'regions']);
        Route::get('series',               [BrowseController::class, 'series']);
        Route::get('categories',           [BrowseController::class, 'categories']);
        Route::get('browse/country-summary', [BrowseController::class, 'countrySummary']);
    });

    // Community submissions — auth + verified email required, rate-limited (5/min per IP)
    Route::middleware(['auth:sanctum', 'throttle:submissions', 'verified'])->group(function () {
        Route::post('plate-requests', [PlateRequestController::class, 'store']);
        Route::post('bug-reports',    [BugReportController::class, 'store']);
    });

    // Community — read/delete own submissions (auth required, general rate limit)
    Route::middleware(['auth:sanctum', 'throttle:api'])->group(function () {
        Route::get('plate-requests',        [PlateRequestController::class, 'index']);
        Route::get('bug-reports',           [BugReportController::class, 'index']);
        Route::delete('plate-requests/{id}', [PlateRequestController::class, 'destroy']);
        Route::delete('bug-reports/{id}',    [BugReportController::class, 'destroy']);
    });

    // Discover — requires auth + verified email (120/min per user)
    Route::middleware(['auth:sanctum', 'throttle:api', 'verified'])->group(function () {
        Route::post('plates/{id}/discover', [PlatesController::class, 'discover']);
    });

    // Purchase + promo verification — auth required, tightly rate-limited (10/min), Play Integrity checked (fail-open v1)
    Route::middleware(['auth:sanctum', 'throttle:auth', CheckPlayIntegrity::class])->group(function () {
        Route::post('auth/purchase/verify', [PurchaseController::class, 'verify']);
        Route::post('auth/promo/redeem',    [PromoController::class, 'redeem']);
    });

    // Authenticated — general rate limit (120/min per user)
    Route::middleware(['auth:sanctum', 'throttle:api'])->group(function () {
        Route::post('auth/logout',          [AuthController::class, 'logout']);
        Route::get('auth/me',               [AuthController::class, 'me']);
        Route::patch('auth/me',             [AuthController::class, 'updateMe']);
        Route::get('auth/collection',                     [CollectionController::class, 'index']);
        Route::get('auth/collection/locations',            [CollectionController::class, 'locations']);
        Route::get('auth/stats',                          [CollectionController::class, 'stats']);
        Route::get('auth/badges',                         [CollectionController::class, 'badges']);
        Route::patch('auth/collection/{id}/notes',        [CollectionController::class, 'updateNotes']);
        Route::patch('auth/collection/{id}/location',     [CollectionController::class, 'updateLocation']);
        Route::delete('auth/collection/{id}',             [CollectionController::class, 'destroy']);
        // Offline metadata pack
        Route::get('offline/metadata', [OfflineController::class, 'metadata']);

        // Discovery sessions
        Route::get('auth/sessions',                 [SessionController::class, 'index']);
        Route::post('auth/sessions',                [SessionController::class, 'store']);
        Route::patch('auth/sessions/{id}',          [SessionController::class, 'update']);
        Route::delete('auth/sessions/{id}',         [SessionController::class, 'destroy']);
        Route::get('auth/sessions/{id}/export',     [SessionController::class, 'export']);
    });
});