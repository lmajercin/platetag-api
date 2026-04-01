<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class PlatesController extends Controller
{
    /**
     * List plates, optionally filtered by state/region.
     * GET /api/v1/plates
     */
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'state'    => ['nullable', 'string', 'max:10'],
            'category' => ['nullable', 'string', 'max:50'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
            'page'     => ['nullable', 'integer', 'min:1'],
        ]);

        // Placeholder — real query wired once plates table migration exists
        return response()->json([
            'data'    => [],
            'message' => 'Plates endpoint active. Schema migration pending.',
        ]);
    }

    /**
     * Return single plate detail.
     * GET /api/v1/plates/{id}
     */
    public function show(int $id): JsonResponse
    {
        // Placeholder
        return response()->json([
            'id'      => $id,
            'message' => 'Plate detail endpoint active. Schema migration pending.',
        ]);
    }

    /**
     * Log a discovery for the authenticated user.
     * POST /api/v1/plates/{id}/discover
     */
    public function discover(Request $request, int $id): JsonResponse
    {
        $request->validate([
            'discovered_at' => ['nullable', 'date_format:Y-m-d\TH:i:s\Z'],
        ]);

        $discoveredAt = $request->input('discovered_at', now()->toISOString());
        $userId       = $request->user()->id;

        // Placeholder — will insert into user_discovered_plates once migrated
        return response()->json([
            'plate_id'      => $id,
            'user_id'       => $userId,
            'discovered_at' => $discoveredAt,
            'message'       => 'Discovery recorded (placeholder).',
        ], 201);
    }
}
