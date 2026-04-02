<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class CollectionController extends Controller
{
    /**
     * Return the authenticated user's discovered plates.
     * GET /api/v1/auth/collection
     */
    public function index(Request $request): JsonResponse
    {
        $user = $request->user();

        $discoveries = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->leftJoin('categories', 'categories.id', '=', 'plates.category_id')
            ->where('udp.user_id', $user->id)
            ->select([
                'udp.id as discovery_id',
                'udp.discovered_at',
                'udp.notes',
                'plates.id as plate_id',
                'plates.name as plate_name',
                'plates.slug as plate_slug',
                'plates.vehicle_class',
                'plates.image_filename',
                'series.id as series_id',
                'series.name as series_name',
                'series.country_code',
                'series.header as series_header',
                'series.footer as series_footer',
                'regions.id as region_id',
                'regions.name as region_name',
                'regions.code as region_code',
                'categories.id as category_id',
                'categories.name as category_name',
            ])
            ->orderByDesc('udp.discovered_at')
            ->paginate(50);

        return response()->json([
            'data' => $discoveries->items(),
            'meta' => [
                'current_page' => $discoveries->currentPage(),
                'last_page'    => $discoveries->lastPage(),
                'per_page'     => $discoveries->perPage(),
                'total'        => $discoveries->total(),
            ],
        ]);
    }

    /**
     * Return collection statistics for the authenticated user.
     * GET /api/v1/auth/stats
     */
    public function stats(Request $request): JsonResponse
    {
        $user = $request->user();

        $row = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->where('udp.user_id', $user->id)
            ->selectRaw('
                COUNT(DISTINCT udp.plate_id)   AS total_plates,
                COUNT(DISTINCT regions.id)     AS total_regions,
                COUNT(DISTINCT series.country_code) AS total_countries
            ')
            ->first();

        return response()->json([
            'total_plates'    => (int) ($row->total_plates    ?? 0),
            'total_regions'   => (int) ($row->total_regions   ?? 0),
            'total_countries' => (int) ($row->total_countries ?? 0),
        ]);
    }
}
