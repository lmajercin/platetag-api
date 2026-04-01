<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\PlatesController;

// ── Public auth routes ────────────────────────────────────────────────────────
Route::prefix('v1')->group(function () {

    Route::prefix('auth')->group(function () {
        Route::post('register', [AuthController::class, 'register']);
        Route::post('login',    [AuthController::class, 'login']);
    });

    // ── Authenticated routes ──────────────────────────────────────────────────
    Route::middleware('auth:sanctum')->group(function () {

        Route::post('auth/logout', [AuthController::class, 'logout']);
        Route::get('auth/me',      [AuthController::class, 'me']);

        Route::get('plates',                  [PlatesController::class, 'index']);
        Route::get('plates/{id}',             [PlatesController::class, 'show']);
        Route::post('plates/{id}/discover',   [PlatesController::class, 'discover']);
    });
});
