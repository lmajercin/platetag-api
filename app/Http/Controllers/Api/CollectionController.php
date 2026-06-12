<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;

class CollectionController extends Controller
{
    private function publicStorageUrl(Request $request, string $folder, ?string $filename): ?string
    {
        if (!$filename) {
            return null;
        }

        $baseUrl = rtrim((string) config('app.url', ''), '/');
        if ($baseUrl === '') {
            $baseUrl = rtrim($request->getSchemeAndHttpHost(), '/');
        }

        return $baseUrl . '/storage/' . $folder . '/' . ltrim($filename, '/');
    }

    /**
     * Return the authenticated user's discovered plates.
     * GET /api/v1/auth/collection
     */
    public function index(Request $request): JsonResponse
    {
        $user = $request->user();

        // Optional session filter
        $sessionId = null;
        if ($request->filled('session_id')) {
            $sessionId = (int) $request->query('session_id');
            $validSession = DB::table('discovery_sessions')
                ->where('id', $sessionId)
                ->where('user_id', $user->id)
                ->exists();
            if (!$validSession) {
                return response()->json(['message' => 'Invalid session.'], 422);
            }
        }

        // Optional search and region filters
        $search   = $request->filled('search') ? trim($request->query('search')) : null;
        $filterRegionId = $request->filled('region_id') ? (int) $request->query('region_id') : null;
        $filterPlateId  = $request->filled('plate_id')  ? (int) $request->query('plate_id')  : null;

        $discoveries = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->leftJoin('categories', 'categories.id', '=', 'plates.category_id')
            ->where('udp.user_id', $user->id)
            ->when($sessionId !== null, fn($q) => $q->where('udp.session_id', $sessionId))
            ->when($search !== null, fn($q) => $q->where('plates.name', 'like', '%' . $search . '%'))
            ->when($filterRegionId !== null, fn($q) => $q->where('regions.id', $filterRegionId))
            ->when($filterPlateId !== null, fn($q) => $q->where('plates.id', $filterPlateId))
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
                'udp.latitude',
                'udp.longitude',
                'udp.location_label',
            ])
            ->orderByDesc('udp.discovered_at')
            ->paginate(min((int) $request->query('per_page', 50), 500));

        $items = collect($discoveries->items())->map(function ($item) use ($request) {
            $item->image_url = $this->publicStorageUrl($request, 'plates', $item->image_filename);

            return $item;
        })->values();

        return response()->json([
            'data' => $items,
            'meta' => [
                'current_page' => $discoveries->currentPage(),
                'last_page'    => $discoveries->lastPage(),
                'per_page'     => $discoveries->perPage(),
                'total'        => $discoveries->total(),
            ],
        ]);
    }

    /**
     * Return lightweight location data for all of the user's discoveries.
     * GET /api/v1/auth/collection/locations
     *
     * Only returns discoveries that have valid coordinates.
     * Designed for map rendering — no pagination, minimal payload.
     */
    public function locations(Request $request): JsonResponse
    {
        $user = $request->user();

        $items = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->where('udp.user_id', $user->id)
            ->whereNotNull('udp.latitude')
            ->whereNotNull('udp.longitude')
            ->select(
                'udp.id as discovery_id',
                'udp.latitude',
                'udp.longitude',
                'udp.location_label',
                'udp.discovered_at',
                'plates.id as plate_id',
                'plates.name as plate_name',
                'plates.image_filename',
            )
            ->orderByDesc('udp.discovered_at')
            ->get()
            ->map(function ($item) use ($request) {
                $item->image_url = $this->publicStorageUrl($request, 'plates', $item->image_filename);
                unset($item->image_filename);
                return $item;
            })
            ->values();

        return response()->json(['data' => $items]);
    }

    /**
     * Return collection statistics for the authenticated user.
     * GET /api/v1/auth/stats
     */
    public function stats(Request $request): JsonResponse
    {
        $user = $request->user();

        // Optional session filter — verify ownership
        $sessionId = null;
        if ($request->filled('session_id')) {
            $sessionId = (int) $request->query('session_id');
            $owned = DB::table('discovery_sessions')
                ->where('id', $sessionId)
                ->where('user_id', $user->id)
                ->exists();
            if (!$owned) {
                return response()->json(['message' => 'Session not found.'], 404);
            }
        }

        // ── Aggregate totals ──────────────────────────────────────────────────
        $q = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->leftJoin('categories', 'categories.id', '=', 'plates.category_id')
            ->where('udp.user_id', $user->id);
        if ($sessionId !== null) $q->where('udp.session_id', $sessionId);

        $row = $q->selectRaw('
                COUNT(DISTINCT udp.plate_id)        AS total_plates,
                COUNT(DISTINCT regions.id)          AS total_regions,
                COUNT(DISTINCT series.country_code) AS total_countries,
                COUNT(DISTINCT categories.id)       AS total_categories,
                MIN(udp.discovered_at)              AS first_discovery,
                MAX(udp.discovered_at)              AS latest_discovery
            ')
            ->first();

        $collectedPlates     = (int) ($row->total_plates     ?? 0);
        $collectedRegions    = (int) ($row->total_regions    ?? 0);
        $collectedCategories = (int) ($row->total_categories ?? 0);
        $collectedCountries  = (int) ($row->total_countries  ?? 0);

        // ── Library totals (active items) ────────────────────────────────────
        $lib = DB::selectOne('
            SELECT
                (SELECT COUNT(*) FROM plates     WHERE is_active = 1) AS total_plates,
                (SELECT COUNT(*) FROM regions    WHERE is_active = 1) AS total_regions,
                (SELECT COUNT(*) FROM categories WHERE is_active = 1) AS total_categories
        ');
        $libPlates     = (int) ($lib->total_plates     ?? 0);
        $libRegions    = (int) ($lib->total_regions    ?? 0);
        $libCategories = (int) ($lib->total_categories ?? 0);

        $pct = fn(int $c, int $t) => $t > 0 ? round(($c / $t) * 100, 1) : 0.0;

        // ── Per-region breakdown ──────────────────────────────────────────────
        $byRegionQ = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->join('regions', 'regions.id', '=', 'series.region_id')
            ->where('udp.user_id', $user->id);
        if ($sessionId !== null) $byRegionQ->where('udp.session_id', $sessionId);

        $byRegion = $byRegionQ
            ->select(
                'regions.name as region_name',
                'series.country_code',
                DB::raw('COUNT(*) as discovery_count'),
                DB::raw('COUNT(DISTINCT udp.plate_id) as unique_plates')
            )
            ->groupBy('regions.id', 'regions.name', 'series.country_code')
            ->orderByDesc('discovery_count')
            ->get()
            ->map(fn($r) => [
                'region_name'    => $r->region_name,
                'country_code'   => $r->country_code,
                'discovery_count'=> (int) $r->discovery_count,
                'unique_plates'  => (int) $r->unique_plates,
            ]);

        // ── Per-country summary ───────────────────────────────────────────────
        $byCountryQ = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->where('udp.user_id', $user->id);
        if ($sessionId !== null) $byCountryQ->where('udp.session_id', $sessionId);

        $byCountry = $byCountryQ
            ->select(
                DB::raw('series.country_code'),
                DB::raw('COUNT(DISTINCT udp.plate_id) as plates'),
                DB::raw('COUNT(DISTINCT regions.id) as regions')
            )
            ->groupBy('series.country_code')
            ->orderByDesc('plates')
            ->get()
            ->map(fn($r) => [
                'country_code' => $r->country_code,
                'plates'       => (int) $r->plates,
                'regions'      => (int) $r->regions,
            ]);

        // ── Recent discovery locations (for map pins — max 25) ──────────────────
        $locationsQ = DB::table('user_discovered_plates as udp')
            ->where('udp.user_id', $user->id)
            ->whereNotNull('udp.latitude')
            ->whereNotNull('udp.longitude');
        if ($sessionId !== null) $locationsQ->where('udp.session_id', $sessionId);

        $recentLocations = $locationsQ
            ->select('udp.latitude', 'udp.longitude', 'udp.discovered_at')
            ->orderByDesc('udp.discovered_at')
            ->limit(25)
            ->get()
            ->map(fn($r) => [
                'latitude'      => (float) $r->latitude,
                'longitude'     => (float) $r->longitude,
                'discovered_at' => $r->discovered_at,
            ]);

        return response()->json([
            'session_id'        => $sessionId,
            'total_plates'      => $collectedPlates,
            'total_regions'     => $collectedRegions,
            'total_countries'   => $collectedCountries,
            'first_discovery'   => $row->first_discovery  ?? null,
            'latest_discovery'  => $row->latest_discovery ?? null,
            'completion'        => [
                'plates'     => ['collected' => $collectedPlates,     'total' => $libPlates,     'percentage' => $pct($collectedPlates,     $libPlates)],
                'regions'    => ['collected' => $collectedRegions,    'total' => $libRegions,    'percentage' => $pct($collectedRegions,    $libRegions)],
                'categories' => ['collected' => $collectedCategories, 'total' => $libCategories, 'percentage' => $pct($collectedCategories, $libCategories)],
            ],
            'by_region'         => $byRegion,
            'by_country'        => $byCountry,
            'recent_locations'  => $recentLocations,
        ]);
    }

    /**
     * Update notes on a discovery.
     * PATCH /api/v1/auth/collection/{id}/notes
     */
    public function updateNotes(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        $request->validate(['notes' => 'nullable|string|max:500']);

        $rows = DB::table('user_discovered_plates')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->update(['notes' => $request->input('notes')]);

        if ($rows === 0) {
            $exists = DB::table('user_discovered_plates')
                ->where('id', $id)->where('user_id', $user->id)->exists();
            if (!$exists) {
                return response()->json(['message' => 'Discovery not found.'], 404);
            }
        }

        return response()->json(['updated' => true]);
    }

    /**
     * Update location on a discovery.
     * PATCH /api/v1/auth/collection/{id}/location
     */
    public function updateLocation(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        $request->validate([
            'latitude'       => 'nullable|numeric|between:-90,90',
            'longitude'      => 'nullable|numeric|between:-180,180',
            'location_label' => 'nullable|string|max:255',
        ]);

        $rows = DB::table('user_discovered_plates')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->update([
                'latitude'       => $request->input('latitude'),
                'longitude'      => $request->input('longitude'),
                'location_label' => $request->input('location_label'),
            ]);

        if ($rows === 0) {
            $exists = DB::table('user_discovered_plates')
                ->where('id', $id)->where('user_id', $user->id)->exists();
            if (!$exists) {
                return response()->json(['message' => 'Discovery not found.'], 404);
            }
        }

        return response()->json(['updated' => true]);
    }

    /**
     * Delete a discovery record.
     * DELETE /api/v1/auth/collection/{id}
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $user = $request->user();

        $rows = DB::table('user_discovered_plates')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->delete();

        if ($rows === 0) {
            return response()->json(['message' => 'Discovery not found.'], 404);
        }

        return response()->json(['deleted' => true]);
    }

    /**
     * Return all badges with the authenticated user's earned status and progress.
     * GET /api/v1/auth/badges
     *
     * Active un-earned badges show progress toward completion.
     * Earned badges (including any that were later deactivated) always appear
     * in the user's history — earned is earned (Audit item #8b).
     * Un-earned inactive badges are excluded from the response.
     */
    public function badges(Request $request): JsonResponse
    {
        $user = $request->user();

        // All badges the user has earned (regardless of is_active).
        $earnedMap = DB::table('user_badges')
            ->where('user_id', $user->id)
            ->pluck('awarded_at', 'badge_id')
            ->all();

        $earnedBadgeIds = array_keys($earnedMap);

        // Fetch: all active badges + any inactive badges the user has already earned.
        $badges = DB::table('badges')
            ->where(function ($q) use ($earnedBadgeIds) {
                $q->where('is_active', true)
                  ->orWhereIn('id', $earnedBadgeIds);
            })
            ->orderBy('sort_order')
            ->get();

        // For geographic badge progress: distinct regions discovered by this user.
        $discoveredRegionIds = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->where('udp.user_id', $user->id)
            ->whereNotNull('series.region_id')
            ->distinct()
            ->pluck('series.region_id')
            ->all();

        $discoveredRegionSet = array_flip($discoveredRegionIds);

        // Required regions per geographic badge (keyed by badge_id) — include name for display.
        $badgeRegions = DB::table('badge_regions')
            ->join('regions', 'regions.id', '=', 'badge_regions.region_id')
            ->whereIn('badge_regions.badge_id', $badges->where('type', 'geographic')->pluck('id'))
            ->select('badge_regions.badge_id', 'badge_regions.region_id', 'regions.name as region_name')
            ->get()
            ->groupBy('badge_id');

        // User's total first-discovery plate count for milestone progress.
        $totalPlates = DB::table('user_discovered_plates')
            ->where('user_id', $user->id)
            ->where('is_first_discovery', true)
            ->count();

        // Required plates per collection badge (keyed by badge_id).
        $collectionBadgeIds = $badges->where('type', 'collection')->pluck('id');
        $badgePlates = DB::table('badge_plates')
            ->join('plates', 'plates.id', '=', 'badge_plates.plate_id')
            ->whereIn('badge_plates.badge_id', $collectionBadgeIds)
            ->select('badge_plates.badge_id', 'badge_plates.plate_id', 'plates.name as plate_name')
            ->get()
            ->groupBy('badge_id');

        // Plate IDs the user has already collected — for collection badge progress.
        $collectedPlateIds = DB::table('user_discovered_plates')
            ->where('user_id', $user->id)
            ->pluck('plate_id')
            ->flip()
            ->all();

        $result = $badges->map(function ($badge) use (
            $earnedMap, $badgeRegions, $discoveredRegionSet, $totalPlates,
            $badgePlates, $collectedPlateIds
        ) {
            $earned     = isset($earnedMap[$badge->id]);
            $awardedAt  = $earned ? $earnedMap[$badge->id] : null;

            if ($badge->type === 'geographic') {
                $required       = $badgeRegions->get($badge->id, collect());
                $totalRequired  = $required->count();
                $earnedRegions  = $required->filter(
                    fn($r) => isset($discoveredRegionSet[$r->region_id])
                )->count();

                $progress = [
                    'earned_regions' => $earnedRegions,
                    'total_regions'  => $totalRequired,
                ];
                $regionNames = $required->pluck('region_name')->sort()->values()->all();
                $plateNames  = [];
            } elseif ($badge->type === 'collection') {
                $required      = $badgePlates->get($badge->id, collect());
                $totalRequired = $required->count();
                $collectedCount = $required->filter(
                    fn($p) => isset($collectedPlateIds[$p->plate_id])
                )->count();

                $progress = [
                    'collected_plates' => $collectedCount,
                    'total_plates'     => $totalRequired,
                ];
                $regionNames = [];
                $plateNames  = $required->pluck('plate_name')->sort()->values()->all();
            } else {
                $progress = [
                    'current'   => $totalPlates,
                    'threshold' => $badge->threshold,
                ];
                $regionNames = [];
                $plateNames  = [];
            }

            return [
                'id'           => $badge->id,
                'slug'         => $badge->slug,
                'name'         => $badge->name,
                'description'  => $badge->description,
                'type'         => $badge->type,
                'icon'         => $badge->icon,
                'sort_order'   => $badge->sort_order,
                'earned'       => $earned,
                'awarded_at'   => $awardedAt,
                'progress'     => $progress,
                'region_names' => $regionNames,
                'plate_names'  => $plateNames,
            ];
        })->values();

        return response()->json(['data' => $result]);
    }
}
