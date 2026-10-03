<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\PlateShareToken;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class PlateShareController extends Controller
{
    // Tokens valid for 72 hours
    private const TOKEN_TTL_HOURS = 72;

    /**
     * POST /api/v1/auth/plates/share
     * Generate a share token for a set of plate IDs from User A's collection.
     */
    public function create(Request $request): JsonResponse
    {
        $request->validate([
            'plate_ids'   => 'required|array|min:1|max:50',
            'plate_ids.*' => 'integer|exists:plates,id',
        ]);

        $user     = $request->user();
        $plateIds = array_values(array_unique($request->plate_ids));

        // Verify all requested plates are actually in User A's collection
        $owned = DB::table('user_discovered_plates')
            ->where('user_id', $user->id)
            ->whereIn('plate_id', $plateIds)
            ->distinct()
            ->pluck('plate_id')
            ->all();

        if (count($owned) === 0) {
            return response()->json(['message' => 'None of the selected plates are in your collection.'], 422);
        }

        // Use owned subset only — silently drop any IDs not in their collection
        $validIds = array_values($owned);
        sort($validIds); // normalize order so token-reuse comparison is order-independent

        // Reuse a recent non-expired token with the same plate set (prevents flood)
        $existing = PlateShareToken::query()
            ->where('created_by', $user->id)
            ->where('expires_at', '>', now())
            ->latest()
            ->first();

        if ($existing) {
            $existingIds = $existing->plate_ids;
            sort($existingIds);
        }

        if ($existing && $existingIds === $validIds) {
            return response()->json([
                'token'      => $existing->token,
                'link'       => "https://platetag.app/share/plates/{$existing->token}",
                'deep_link'  => "platetag://share/plates/{$existing->token}",
                'expires_at' => $existing->expires_at->toISOString(),
                'plate_count' => count($validIds),
            ]);
        }

        $token = Str::random(48);

        PlateShareToken::create([
            'created_by' => $user->id,
            'token'      => $token,
            'plate_ids'  => $validIds,
            'expires_at' => now()->addHours(self::TOKEN_TTL_HOURS),
        ]);

        return response()->json([
            'token'       => $token,
            'link'        => "https://platetag.app/share/plates/{$token}",
            'deep_link'   => "platetag://share/plates/{$token}",
            'expires_at'  => now()->addHours(self::TOKEN_TTL_HOURS)->toISOString(),
            'plate_count' => count($validIds),
        ]);
    }

    /**
     * GET /api/v1/share/plates/{token}
     * Public preview — no auth required.
     * Returns sharer's first name, plate count, and plate details.
     */
    public function preview(string $token): JsonResponse
    {
        $record = PlateShareToken::query()->where('token', $token)->first();

        if (! $record) {
            return response()->json(['message' => 'Share link not found.'], 404);
        }

        if ($record->isExpired()) {
            return response()->json(['message' => 'This share link has expired.', 'expired' => true], 410);
        }

        $sharer     = DB::table('users')->where('id', $record->created_by)->first();
        $sharerName = $sharer ? explode(' ', trim($sharer->name))[0] : 'Someone';

        $plates = DB::table('plates')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->whereIn('plates.id', $record->plate_ids)
            ->where('plates.is_active', true)
            ->select([
                'plates.id',
                'plates.name',
                'series.name as series_name',
                'series.country_code',
                'regions.name as region_name',
                'regions.code as region_code',
                'plates.image_filename',
            ])
            ->get()
            ->map(fn ($p) => [
                'id'             => $p->id,
                'name'           => $p->name,
                'series_name'    => $p->series_name,
                'country_code'   => $p->country_code,
                'region_name'    => $p->region_name,
                'region_code'    => $p->region_code,
                'image_filename' => $p->image_filename,
            ]);

        return response()->json([
            'sharer_name' => $sharerName,
            'plate_count' => count($record->plate_ids),
            'expires_at'  => $record->expires_at->toISOString(),
            'plates'      => $plates,
        ]);
    }

    /**
     * POST /api/v1/share/plates/{token}/claim
     * Authenticated — imports the shared plates into User B's collection.
     * Enforces free-tier cap. Skips duplicates silently.
     */
    public function claim(Request $request, string $token): JsonResponse
    {
        $userB  = $request->user();
        $record = PlateShareToken::query()->where('token', $token)->first();

        if (! $record) {
            return response()->json(['message' => 'Share link not found.'], 404);
        }

        if ($record->isExpired()) {
            return response()->json(['message' => 'This share link has expired.', 'expired' => true], 410);
        }

        // Block self-claim
        if ($record->created_by === $userB->id) {
            return response()->json(['message' => 'You cannot import your own shared plates.'], 422);
        }

        $sharedPlateIds = $record->plate_ids;

        if (empty($sharedPlateIds)) {
            return response()->json(['added' => 0, 'skipped' => 0]);
        }

        $result = DB::transaction(function () use ($userB, $sharedPlateIds) {
            // Lock user row to prevent concurrent double-import
            DB::table('users')->where('id', $userB->id)->lockForUpdate()->first();

            // Plates User B already has
            $existingPlateIds = DB::table('user_discovered_plates')
                ->where('user_id', $userB->id)
                ->whereIn('plate_id', $sharedPlateIds)
                ->pluck('plate_id')
                ->flip()
                ->all();

            $defaultSession = DB::table('discovery_sessions')
                ->where('user_id', $userB->id)
                ->where('is_default', true)
                ->value('id');

            // B-2: Guard against missing default session — plates with session_id=null
            // would be invisible in the app's session UI.
            if ($defaultSession === null) {
                return ['error' => 'no_default_session'];
            }

            $now  = now();
            $rows = [];

            foreach ($sharedPlateIds as $plateId) {
                if (isset($existingPlateIds[$plateId])) {
                    continue; // already in User B's collection — skip
                }
                $rows[] = [
                    'user_id'            => $userB->id,
                    'plate_id'           => $plateId,
                    'session_id'         => $defaultSession,
                    'discovered_at'      => $now,
                    'is_first_discovery' => true,
                    'latitude'           => null,
                    'longitude'          => null,
                    'location_label'     => null,
                    'notes'              => null,
                    'created_at'         => $now,
                    'updated_at'         => $now,
                ];
            }

            // Enforce free-tier cap
            if (! $userB->is_premium && ! empty($rows)) {
                $currentCount   = DB::table('user_discovered_plates')
                    ->where('user_id', $userB->id)
                    ->distinct('plate_id')
                    ->count('plate_id');
                $remainingSlots = max(0, 50 - $currentCount);
                if ($remainingSlots <= 0) {
                    return ['cap_reached' => true];
                }
                $rows = array_slice($rows, 0, $remainingSlots);
            }

            if (! empty($rows)) {
                DB::table('user_discovered_plates')->insert($rows);
            }

            return ['added' => count($rows), 'skipped' => count($sharedPlateIds) - count($rows)];
        });

        if (! empty($result['error'])) {
            return response()->json(['message' => 'Could not find your default collection. Please open the PlateTag app once to set it up.'], 422);
        }

        if (! empty($result['cap_reached'])) {
            return response()->json([
                'message'   => 'Free plan plate limit reached. Upgrade to Full Access to import more plates.',
                'cap_reached' => true,
            ], 422);
        }

        return response()->json([
            'added'   => $result['added'],
            'skipped' => $result['skipped'],
        ]);
    }
}
