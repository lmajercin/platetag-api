<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\BrowseController;
use App\Http\Controllers\Api\BugReportController;
use App\Http\Controllers\Api\CollectionController;
use App\Http\Controllers\Api\PlatesController;
use App\Http\Controllers\Api\PlateRequestController;

Route::prefix('v1')->group(function () {

    // Public auth
    Route::prefix('auth')->group(function () {
        Route::post('register', [AuthController::class, 'register']);
        Route::post('login',    [AuthController::class, 'login']);
    });

    // Public browse
    Route::get('plates',      [PlatesController::class, 'index']);
    Route::get('plates/{id}', [PlatesController::class, 'show']);
    Route::get('regions',     [BrowseController::class, 'regions']);
    Route::get('series',      [BrowseController::class, 'series']);
    Route::get('categories',  [BrowseController::class, 'categories']);

    // Community submissions � allowed unauthenticated (user_id nullable)
    Route::post('plate-requests', [PlateRequestController::class, 'store']);
    Route::post('bug-reports',    [BugReportController::class, 'store']);

    // Authenticated
    Route::middleware('auth:sanctum')->group(function () {
        Route::post('auth/logout',          [AuthController::class, 'logout']);
        Route::get('auth/me',               [AuthController::class, 'me']);
        Route::get('auth/collection',       [CollectionController::class, 'index']);
        Route::get('auth/stats',            [CollectionController::class, 'stats']);
        Route::post('plates/{id}/discover', [PlatesController::class, 'discover']);
    });
});
