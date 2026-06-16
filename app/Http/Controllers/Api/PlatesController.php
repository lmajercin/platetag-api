<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Plate;
use App\Services\BadgeService;
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

        $baseUrl = rtrim((string) config('app.url', ''), '/');
        if ($baseUrl === '') {
            // Local fallback when APP_URL is not configured.
            $baseUrl = rtrim($request->getSchemeAndHttpHost(), '/');
        }

        return $baseUrl . '/storage/' . $folder . '/' . ltrim($filename, '/');
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
            // Split on whitespace so multi-word queries like "Texas Navy" or "California UCLA"
            // require each token to match independently across any searchable field,
            // rather than looking for the whole phrase as one literal substring.
            $tokens = preg_split('/\s+/', trim($request->query('search')), -1, PREG_SPLIT_NO_EMPTY);
            foreach ($tokens as $token) {
                $term = '%' . $token . '%';
                $query->where(function ($q) use ($term) {
                    $q->where('plates.name', 'like', $term)
                      ->orWhere('plates.detail', 'like', $term)
                      ->orWhere('plates.footer_override', 'like', $term)
                      ->orWhere('plates.tags', 'like', $term)
                      ->orWhereHas('series', fn ($s) => $s->where('name', 'like', $term))
                      ->orWhereHas('series.region', fn ($r) => $r->where('name', 'like', $term)
                                                                  ->orWhere('code', 'like', $term));
                });
            }
        }

        $perPage = (int) $request->query('per_page', 50);

        // When browsing a specific series, region, or country (not a text search),
        // float primary plate first, then secondary plates, then the rest — all alphabetical within each tier.
        $isBrowse = !$request->filled('search');
        if ($isBrowse) {
            $query->orderByDesc('plates.is_primary')
                  ->orderByDesc('plates.is_secondary')
                  ->orderBy('plates.name');
        } else {
            $query->orderBy('plates.name');
        }

        $plates  = $query->paginate($perPage);
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
        $plate = Plate::with(['series.region', 'category'])
            ->where('is_active', true)
            ->findOrFail($id);
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
     *
     * Re-discovery is allowed — each sighting is a separate row.
     * is_first_discovery = true only on the first row for this user+plate combination.
     *
     * Free users are capped at config('app.free_plate_cap') unique first-discoveries.
     * Re-discovering an already-owned plate does NOT count against the cap.
     * Cap check uses a pessimistic lock (lockForUpdate) to prevent race conditions
     * where concurrent requests could push a free user past the limit.
     */
    public function discover(Request $request, int $id): JsonResponse
    {
        $request->validate([
            'discovered_at'  => ['nullable', 'date_format:Y-m-d\TH:i:s\Z'],
            'notes'          => ['nullable', 'string', 'max:500'],
            'latitude'       => ['nullable', 'numeric', 'between:-90,90'],
            'longitude'      => ['nullable', 'numeric', 'between:-180,180'],
            'location_label' => ['nullable', 'string', 'max:255'],
            'session_id'     => ['nullable', 'integer'],
        ]);

        $plate = Plate::where('is_active', true)->findOrFail($id);
        $user  = $request->user();

        // Validate session_id belongs to this user (if provided).
        // If not provided, fall back to the user's most recent open session.
        $sessionId = null;
        if ($request->filled('session_id')) {
            $sessionId = (int) $request->input('session_id');
            $validSession = DB::table('discovery_sessions')
                ->where('id', $sessionId)
                ->where('user_id', $user->id)
                ->exists();
            if (!$validSession) {
                return response()->json(['message' => 'Invalid session.'], 422);
            }
        } else {
            $fallback = DB::table('discovery_sessions')
                ->where('user_id', $user->id)
                ->whereNull('ended_at')
                ->orderByDesc('created_at')
                ->value('id');
            $sessionId = $fallback ?? null;
        }

        $discoveredAt = $request->input('discovered_at')
            ? \Carbon\Carbon::parse($request->input('discovered_at'))
            : now();

        // Enforce premium/cap decision and insert atomically to prevent TOCTOU races.
        $insertData = [
            'session_id'     => $sessionId,
            'discovered_at'  => $discoveredAt,
            'notes'          => $request->input('notes'),
            'latitude'       => $request->input('latitude'),
            'longitude'      => $request->input('longitude'),
            'location_label' => $request->input('location_label'),
            'created_at'     => now(),
            'updated_at'     => now(),
        ];

        $result = DB::transaction(function () use ($user, $plate, $insertData) {
            // This FOR UPDATE lock on the users row is the serialization mutex for all
            // concurrent discover() requests from this user. Both requests will block
            // here until the first one commits. Do NOT remove — without it, two
            // concurrent requests can both pass the cap check and both insert.
            $isPremium = (bool) DB::table('users')
                ->where('id', $user->id)
                ->lockForUpdate()
                ->value('is_premium');

            $alreadyOwned = DB::table('user_discovered_plates')
                ->where('user_id', $user->id)
                ->where('plate_id', $plate->id)
                ->lockForUpdate()
                ->exists();

            $isFirst = ! $alreadyOwned;

            // Only free users creating a brand-new first discovery are capped.
            if (! $isPremium && $isFirst) {
                $firstDiscoveryCount = DB::table('user_discovered_plates')
                    ->where('user_id', $user->id)
                    ->where('is_first_discovery', true)
                    ->lockForUpdate()
                    ->count();

                if ($firstDiscoveryCount >= config('app.free_plate_cap', 50)) {
                    return null; // Signal: cap exceeded
                }
            }

            $rowId = DB::table('user_discovered_plates')->insertGetId(array_merge($insertData, [
                'user_id'            => $user->id,
                'plate_id'           => $plate->id,
                'is_first_discovery' => $isFirst,
            ]));

            return ['rowId' => $rowId, 'isFirst' => $isFirst];
        });

        if ($result === null) {
            return response()->json([
                'message'          => 'Free collection limit reached. Upgrade to PlateTag Full to continue.',
                'upgrade_required' => true,
            ], 403);
        }

        $rowId   = $result['rowId'];
        $isFirst = $result['isFirst'];

        // Badge check runs outside the transaction (read-heavy, non-critical for atomicity).
        $badgeService = new BadgeService();
        $newBadges    = $badgeService->checkAfterDiscovery($user, $plate);
        $badgesEarned = $newBadges->map(fn($b) => [
            'id'   => $b->id,
            'name' => $b->name,
            'icon' => $b->icon,
        ])->values();

        return response()->json([
            'id'                 => $rowId,
            'plate_id'           => $plate->id,
            'discovered'         => true,
            'is_first_discovery' => $isFirst,
            'discovered_at'      => $discoveredAt->toISOString(),
            'badges_earned'      => $badgesEarned,
        ], 201);
    }
}

