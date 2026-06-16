<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class OfflineController extends Controller
{
    /**
     * Return a flat metadata pack for offline caching.
     * GET /api/v1/offline/metadata
     *
     * Contains all active plates, series, regions, and categories.
     * Image URLs are absolute so the app can download them directly.
     * metadata_version is the MAX updated_at timestamp of the plates table —
     * the app compares this to its stored version to decide whether to refresh.
     */
    public function metadata(Request $request): JsonResponse
    {
        $baseUrl = rtrim(config('app.url'), '/');

        // All active plates — flat select, no eager loading
        $plates = DB::table('plates')
            ->where('is_active', true)
            ->select('id', 'name', 'slug', 'series_id', 'category_id', 'image_filename')
            ->orderBy('id')
            ->get()
            ->map(function ($plate) use ($baseUrl) {
                return [
                    'id'           => $plate->id,
                    'name'         => $plate->name,
                    'slug'         => $plate->slug,
                    'series_id'    => $plate->series_id,
                    'category_id'  => $plate->category_id,
                    'image_url'    => $plate->image_filename
                        ? $baseUrl . '/storage/plates/' . ltrim($plate->image_filename, '/')
                        : null,
                ];
            });

        // All active series
        $series = DB::table('series')
            ->where('is_active', true)
            ->select('id', 'name', 'slug', 'region_id', 'country_code',
                     'header', 'footer', 'background')
            ->orderBy('id')
            ->get();

        // All active regions
        $regions = DB::table('regions')
            ->where('is_active', true)
            ->select('id', 'name', 'code', 'country_code')
            ->orderBy('id')
            ->get();

        // All active categories
        $categories = DB::table('categories')
            ->where('is_active', true)
            ->select('id', 'name')
            ->orderBy('id')
            ->get();

        // Version stamp — latest updated_at from plates table
        $metadataVersion = DB::table('plates')
            ->where('is_active', true)
            ->max('updated_at');

        return response()->json([
            'metadata_version' => $metadataVersion,
            'plates'           => $plates,
            'series'           => $series,
            'regions'          => $regions,
            'categories'       => $categories,
        ]);
    }
}
