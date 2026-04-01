<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Plate;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class PlatesController extends Controller
{
    /**
     * List plates, optionally filtered by state/country.
     * GET /api/v1/plates
     */
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'state'    => ['nullable', 'string', 'max:10'],
            'country'  => ['nullable', 'string', 'max:10'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
            'page'     => ['nullable', 'integer', 'min:1'],
        ]);

        $query = Plate::where('is_active', true)
            ->select('id', 'state_code', 'country_code', 'plate_type', 'name', 'slug', 'image_filename', 'year_introduced');

        if ($request->filled('state')) {
            $query->where('state_code', strtoupper($request->query('state')));
        }

        if ($request->filled('country')) {
            $query->where('country_code', strtoupper($request->query('country')));
        }

        $perPage = (int) $request->query('per_page', 50);
        $plates  = $query->orderBy('state_code')->orderBy('name')->paginate($perPage);

        return response()->json($plates);
    }

    /**
     * Return single plate detail.
     * GET /api/v1/plates/{id}
     */
    public function show(int $id): JsonResponse
    {
        $plate = Plate::findOrFail($id);

        return response()->json($plate);
    }

    /**
     * Log a discovery for the authenticated user.
     * POST /api/v1/plates/{id}/discover
     */
    public function discover(Request $request, int $id): JsonResponse
    {
        $request->validate([
            'discovered_at' => ['nullable', 'date_format:Y-m-d\TH:i:s\Z'],
            'notes'         => ['nullable', 'string', 'max:500'],
        ]);

        $plate = Plate::findOrFail($id);
        $user  = $request->user();

        $alreadyDiscovered = DB::table('user_discovered_plates')
            ->where('user_id', $user->id)
            ->where('plate_id', $plate->id)
            ->exists();

        if ($alreadyDiscovered) {
            return response()->json([
                'plate_id'   => $plate->id,
                'discovered' => false,
                'message'    => 'Already in your collection.',
            ]);
        }

        $discoveredAt = $request->input('discovered_at')
            ? \Carbon\Carbon::parse($request->input('discovered_at'))
            : now();

        DB::table('user_discovered_plates')->insert([
            'user_id'       => $user->id,
            'plate_id'      => $plate->id,
            'discovered_at' => $discoveredAt,
            'notes'         => $request->input('notes'),
            'created_at'    => now(),
            'updated_at'    => now(),
        ]);

        return response()->json([
            'plate_id'      => $plate->id,
            'discovered'    => true,
            'discovered_at' => $discoveredAt->toISOString(),
        ], 201);
    }
}

