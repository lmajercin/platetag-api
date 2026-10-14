<?php

use App\Http\Middleware\CheckPlayIntegrity;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\BrowseController;
use App\Http\Controllers\Api\BugReportController;
use App\Http\Controllers\Api\CollectionController;
use App\Http\Controllers\Api\GameController;
use App\Http\Controllers\Api\GroupController;
use App\Http\Controllers\Api\GroupInviteController;
use App\Http\Controllers\Api\GroupLeaderboardController;
use App\Http\Controllers\Api\OfflineController;
use App\Http\Controllers\Api\PlatesController;
use App\Http\Controllers\Api\PlateRequestController;
use App\Http\Controllers\Api\PromoController;
use App\Http\Controllers\Api\PurchaseController;
use App\Http\Controllers\Api\SessionController;
use App\Http\Controllers\Api\SessionShareController;
use App\Http\Controllers\Api\PlateShareController;
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

    // Session share — public preview (no auth), tight rate limit (30/min per IP)
    Route::middleware('throttle:auth')->prefix('share')->group(function () {
        Route::get('session/{token}',        [SessionShareController::class, 'preview']);
        Route::get('plates/{token}',         [PlateShareController::class,  'preview']);
    });

    // Group invite — public preview (no auth), tight rate limit (30/min per IP)
    Route::middleware('throttle:auth')->group(function () {
        Route::get('groups/invite/{token}', [GroupInviteController::class, 'preview']);
    });

    // Session share — claim requires auth (30/min per user)
    Route::middleware(['auth:sanctum', 'throttle:auth'])->prefix('share')->group(function () {
        Route::post('session/{token}/claim', [SessionShareController::class, 'claim']);
        Route::post('plates/{token}/claim',  [PlateShareController::class,  'claim']);
    });

    // Public browse — general rate limit (60/min per IP)
    Route::middleware('throttle:api')->group(function () {
        Route::get('plates',               [PlatesController::class, 'index']);
        Route::get('plates/global-stats',  [BrowseController::class, 'globalStats']); // must precede plates/{id}
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
        Route::post('auth/sessions/{id}/share',     [SessionShareController::class, 'create']);
        Route::post('auth/plates/share',             [PlateShareController::class,  'create']);

        // ── Groups (Build 87a) ───────────────────────────────────────────────
        // Groups CRUD
        Route::get('groups',                         [GroupController::class, 'index']);
        Route::post('groups',                        [GroupController::class, 'store']);
        Route::get('groups/{id}',                    [GroupController::class, 'show']);
        Route::patch('groups/{id}',                  [GroupController::class, 'update']);
        Route::delete('groups/{id}',                 [GroupController::class, 'destroy']);
        Route::post('groups/{id}/leave',             [GroupController::class, 'leave']);
        Route::post('groups/{id}/transfer',          [GroupController::class, 'transferLeadership']);
        Route::delete('groups/{id}/members/{memberId}', [GroupController::class, 'removeMember']);
        Route::get('groups/{id}/members',            [GroupController::class, 'members']);

        // Invite tokens
        Route::post('groups/{id}/invite',            [GroupInviteController::class, 'generate']);
        Route::post('groups/invite/{token}/join',    [GroupInviteController::class, 'join']);

        // Leaderboard + state map
        Route::get('groups/{id}/leaderboard',        [GroupLeaderboardController::class, 'index']);
        Route::get('groups/{id}/members/{userId}/plates', [GroupLeaderboardController::class, 'memberPlates']);
        Route::get('groups/{id}/state-map',          [GroupLeaderboardController::class, 'stateMap']);

        // Games — read + edit (standard API rate limit)
        Route::get('groups/{groupId}/games',         [GameController::class, 'index']);
        Route::get('groups/{groupId}/games/{id}',    [GameController::class, 'show']);
        Route::patch('groups/{groupId}/games/{id}',  [GameController::class, 'update']);

        // Games — create + finalize (stricter rate limit per @Audit GO 2026-10-13)
        Route::middleware('throttle:games')->group(function () {
            Route::post('groups/{groupId}/games',                 [GameController::class, 'store']);
            Route::post('groups/{groupId}/games/{id}/finalize',   [GameController::class, 'finalize']);
        });
    });
});