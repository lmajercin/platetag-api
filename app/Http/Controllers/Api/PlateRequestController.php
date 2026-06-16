<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\PlateRequest;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class PlateRequestController extends Controller
{
    /**
     * List the authenticated user's own plate requests.
     * GET /api/v1/plate-requests
     */
    public function index(Request $request): JsonResponse
    {
        $requests = PlateRequest::where('user_id', $request->user()->id)
            ->orderByDesc('created_at')
            ->get(['id', 'plate_name', 'region_hint', 'status', 'admin_reply', 'created_at', 'resolved_at']);

        return response()->json($requests);
    }

    /**
     * Submit a new plate addition request.
     * POST /api/v1/plate-requests
     */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'plate_name'  => ['required', 'string', 'max:191'],
            'region_hint' => ['nullable', 'string', 'max:191'],
            'description' => ['nullable', 'string', 'max:2000'],
        ]);

        $plateRequest = PlateRequest::create([
            'user_id'     => $request->user()?->id,
            'plate_name'  => $data['plate_name'],
            'region_hint' => $data['region_hint'] ?? null,
            'description' => $data['description'] ?? null,
            'status'      => 'pending',
        ]);

        return response()->json([
            'id'      => $plateRequest->id,
            'message' => 'Request submitted. We\'ll review it soon.',
        ], 201);
    }

    /**
     * Delete the authenticated user's own plate request.
     * DELETE /api/v1/plate-requests/{id}
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $plateRequest = PlateRequest::where('id', $id)
            ->where('user_id', $request->user()->id)
            ->first();

        if (!$plateRequest) {
            return response()->json(['message' => 'Not found'], 404);
        }

        $plateRequest->delete();

        return response()->json(['message' => 'Deleted']);
    }
}
