<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Plate;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class PlatesController extends Controller
{
    private function publicStorageUrl(Request $request, string $folder, ?string $filename): ?string
    {
        if (!$filename) {
            return null;
        }

        return rtrim($request->root(), '/') . '/storage/' . $folder . '/' . ltrim($filename, '/');
    }

    /**
     * List plates with optional filters.
     * GET /api/v1/plates
     *
     * Query params:
     *   series_id, region_id, country_code, category_id, vehicle_class, search, per_page, page
     */
    public function index(Request $request): JsonResponse
    {
        $request->validate([
            'series_id'    => ['nullable', 'integer'],
            'region_id'    => ['nullable', 'integer'],
            'country_code' => ['nullable', 'string', 'max:10'],
            'category_id'  => ['nullable', 'integer'],
            'vehicle_class'=> ['nullable', 'string', 'max:50'],
            'search'       => ['nullable', 'string', 'max:100'],
            'per_page'     => ['nullable', 'integer', 'min:1', 'max:100'],
            'page'         => ['nullable', 'integer', 'min:1'],
        ]);

        $query = Plate::with(['series:id,name,country_code,header,footer,background,region_id',
                              'series.region:id,name,code,country_code',
                              'category:id,name'])
            ->where('plates.is_active', true);

        if ($request->filled('series_id')) {
            $query->where('series_id', $request->integer('series_id'));
        }

        if ($request->filled('region_id')) {
            $query->whereHas('series', fn ($q) => $q->where('region_id', $request->integer('region_id')));
        }

        if ($request->filled('country_code')) {
            $query->whereHas('series', fn ($q) => $q->where('country_code', strtoupper($request->query('country_code'))));
        }

        if ($request->filled('category_id')) {
            $query->where('category_id', $request->integer('category_id'));
        }

        if ($request->filled('vehicle_class')) {
            $query->where('vehicle_class', $request->query('vehicle_class'));
        }

        if ($request->filled('search')) {
            $query->where('name', 'like', '%' . $request->query('search') . '%');
        }

        $perPage = (int) $request->query('per_page', 50);
        $plates  = $query->orderBy('name')->paginate($perPage);
        $items = collect($plates->items())->map(function (Plate $plate) use ($request) {
            $plate->image_url = $this->publicStorageUrl($request, 'plates', $plate->image_filename);

            if ($plate->series) {
                $plate->series->image_url = $this->publicStorageUrl($request, 'series', $plate->series->image_filename);
            }

            return $plate;
        })->values();

        return response()->json([
            'data' => $items,
            'meta' => [
                'current_page' => $plates->currentPage(),
                'last_page'    => $plates->lastPage(),
                'per_page'     => $plates->perPage(),
                'total'        => $plates->total(),
                'from'         => $plates->firstItem(),
                'to'           => $plates->lastItem(),
            ],
        ]);
    }

    /**
     * Return single plate detail.
     * GET /api/v1/plates/{id}
     */
    public function show(int $id): JsonResponse
    {
        $plate = Plate::with(['series.region', 'category'])->findOrFail($id);
        $request = request();

        $plate->image_url = $this->publicStorageUrl($request, 'plates', $plate->image_filename);

        if ($plate->series) {
            $plate->series->image_url = $this->publicStorageUrl($request, 'series', $plate->series->image_filename);
        }

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

