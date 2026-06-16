<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Category;
use App\Models\Region;
use App\Models\Series;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class BrowseController extends Controller
{
    private function publicStorageUrl(Request $request, string $folder, ?string $filename): ?string
    {
        if (!$filename) {
            return null;
        }

        return rtrim($request->getSchemeAndHttpHost(), '/') . '/storage/' . $folder . '/' . ltrim($filename, '/');
    }

    /**
     * List active regions.
     * GET /api/v1/regions
     */
    public function regions(Request $request): JsonResponse
    {
        $request->validate([
            'country_code' => ['nullable', 'string', 'max:10'],
        ]);

        $user = auth('sanctum')->user();

        $query = Region::where('is_active', true)
            ->select('id', 'name', 'code', 'country_code', 'capital_city', 'capital_lat', 'capital_lng')
            ->addSelect(DB::raw(
                '(SELECT COUNT(p.id) FROM plates p'
                . ' JOIN series s ON s.id = p.series_id'
                . ' WHERE s.region_id = regions.id AND p.is_active = 1) as plate_count'
            ));

        if ($request->filled('country_code')) {
            $query->where('country_code', strtoupper($request->query('country_code')));
        }

        // Collect region IDs for a single discovered-count query
        $items = $query->orderBy('name')->get();

        if ($user) {
            $regionIds = $items->pluck('id');
            $discovered = DB::table('user_discovered_plates as udp')
                ->join('plates', 'plates.id', '=', 'udp.plate_id')
                ->join('series', 'series.id', '=', 'plates.series_id')
                ->whereIn('series.region_id', $regionIds)
                ->where('udp.user_id', $user->id)
                ->selectRaw('series.region_id, COUNT(DISTINCT udp.plate_id) as cnt')
                ->groupBy('series.region_id')
                ->pluck('cnt', 'series.region_id');

            $items->each(function ($region) use ($discovered) {
                $region->discovered_count = (int) ($discovered[$region->id] ?? 0);
            });
        }

        $items = $items->map(function (Region $region) use ($request) {
            $region->image_url = $this->publicStorageUrl($request, 'regions', $region->image_filename ?? null);
            return $region;
        });

        return response()->json($items);
    }

    /**
     * List active series.
     * GET /api/v1/series
     */
    public function series(Request $request): JsonResponse
    {
        $request->validate([
            'region_id'    => ['nullable', 'integer'],
            'country_code' => ['nullable', 'string', 'max:10'],
        ]);

        $user = auth('sanctum')->user();

        $query = Series::with('region:id,name,code,country_code')
            ->where('is_active', true)
            ->withCount(['plates as plate_count' => function ($q) {
                $q->where('is_active', true);
            }])
            ->select('id', 'name', 'slug', 'region_id', 'country_code',
                     'header', 'footer', 'background', 'year_start', 'year_end', 'image_filename');

        if ($request->filled('region_id')) {
            $query->where('region_id', $request->integer('region_id'));
        }

        if ($request->filled('country_code')) {
            $query->where('country_code', strtoupper($request->query('country_code')));
        }

        $items = $query->orderBy('name')->get();

        if ($user) {
            $seriesIds = $items->pluck('id');
            $discovered = DB::table('user_discovered_plates as udp')
                ->join('plates', 'plates.id', '=', 'udp.plate_id')
                ->whereIn('plates.series_id', $seriesIds)
                ->where('udp.user_id', $user->id)
                ->selectRaw('plates.series_id, COUNT(DISTINCT udp.plate_id) as cnt')
                ->groupBy('plates.series_id')
                ->pluck('cnt', 'plates.series_id');

            $items->each(function ($series) use ($discovered) {
                $series->discovered_count = (int) ($discovered[$series->id] ?? 0);
            });
        }

        return response()->json($items);
    }

    /**
     * Per-country plate totals and (if authenticated) discovered counts.
     * GET /api/v1/browse/country-summary
     */
    public function countrySummary(Request $request): JsonResponse
    {
        $user = auth('sanctum')->user();

        $totals = DB::table('plates')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->where('plates.is_active', true)
            ->selectRaw('series.country_code, COUNT(plates.id) as plate_count')
            ->groupBy('series.country_code')
            ->pluck('plate_count', 'series.country_code');

        $discovered = collect();
        if ($user) {
            $discovered = DB::table('user_discovered_plates as udp')
                ->join('plates', 'plates.id', '=', 'udp.plate_id')
                ->join('series', 'series.id', '=', 'plates.series_id')
                ->where('udp.user_id', $user->id)
                ->selectRaw('series.country_code, COUNT(DISTINCT udp.plate_id) as cnt')
                ->groupBy('series.country_code')
                ->pluck('cnt', 'series.country_code');
        }

        // Build combined result for every country that has plates
        $result = $totals->map(function ($count, $code) use ($discovered) {
            return [
                'country_code'     => $code,
                'plate_count'      => (int) $count,
                'discovered_count' => (int) ($discovered[$code] ?? 0),
            ];
        })->values();

        return response()->json($result);
    }

    /**
     * List all categories.
     * GET /api/v1/categories
     */
    public function categories(): JsonResponse
    {
        $categories = Category::select('id', 'name')->where('is_active', true)->orderBy('name')->get();
        return response()->json($categories);
    }
}
