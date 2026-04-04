<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Category;
use App\Models\Region;
use App\Models\Series;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class BrowseController extends Controller
{
    private function publicStorageUrl(Request $request, string $folder, ?string $filename): ?string
    {
        if (!$filename) {
            return null;
        }

        return rtrim($request->root(), '/') . '/storage/' . $folder . '/' . ltrim($filename, '/');
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

        $query = Region::where('is_active', true)
            ->select('id', 'name', 'code', 'country_code', 'capital_city', 'capital_lat', 'capital_lng');

        if ($request->filled('country_code')) {
            $query->where('country_code', strtoupper($request->query('country_code')));
        }

        $items = $query->orderBy('name')->get()->map(function (Series $series) use ($request) {
            $series->image_url = $this->publicStorageUrl($request, 'series', $series->image_filename);
            return $series;
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

        $query = Series::with('region:id,name,code,country_code')
            ->where('is_active', true)
            ->select('id', 'name', 'slug', 'region_id', 'country_code',
                     'header', 'footer', 'background', 'year_start', 'year_end', 'image_filename');

        if ($request->filled('region_id')) {
            $query->where('region_id', $request->integer('region_id'));
        }

        if ($request->filled('country_code')) {
            $query->where('country_code', strtoupper($request->query('country_code')));
        }

        return response()->json($query->orderBy('name')->get());
    }

    /**
     * List all categories.
     * GET /api/v1/categories
     */
    public function categories(): JsonResponse
    {
        $categories = Category::select('id', 'name')->orderBy('name')->get();
        return response()->json($categories);
    }
}
