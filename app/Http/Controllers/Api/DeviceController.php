<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\UserDevice;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

// @Audit GO: 2026-10-27 — Build 91 (5a).
// Registers or refreshes an Expo push token for the authenticated user.
// Route: POST /auth/devices — middleware: auth:sanctum, throttle:api (120/min).
// Idempotent: updateOrCreate on (user_id, platform) means repeated calls are safe.

class DeviceController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'push_token' => ['required', 'string', 'max:255'],
            'platform'   => ['required', 'in:ios,android'],
        ]);

        $user = $request->user();

        UserDevice::updateOrCreate(
            ['user_id' => $user->id, 'platform' => $validated['platform']],
            ['push_token' => $validated['push_token']]
        );

        return response()->json(null, 204);
    }
}
