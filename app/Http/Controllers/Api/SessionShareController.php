<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\SessionShareToken;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class SessionShareController extends Controller
{
    // Tokens are valid for 72 hours from creation
    private const TOKEN_TTL_HOURS = 72;

    /**
     * POST /api/v1/auth/sessions/{id}/share
     * Generate a share token for the authenticated user's session.
     */
    public function create(Request $request, int $id): JsonResponse
    {
        $user = $request->user();

        $session = DB::table('discovery_sessions')
            ->where('id', $id)
            ->where('user_id', $user->id)
            ->first();

        if (! $session) {
            return response()->json(['message' => 'Session not found.'], 404);
        }

        $plateCount = DB::table('user_discovered_plates')
            ->where('user_id', $user->id)
            ->where('session_id', $id)
            ->distinct('plate_id')
            ->count('plate_id');

        if ($plateCount === 0) {
            return response()->json(['message' => 'Cannot share an empty session.'], 422);
        }

        // Reuse an existing non-expired token for this session/user pair to avoid flood
        $existing = SessionShareToken::query()
            ->where('session_id', $id)
            ->where('created_by', $user->id)
            ->where('expires_at', '>', now())
            ->latest()
            ->first();

        if ($existing) {
            return response()->json([
                'token'      => $existing->token,
                'link'       => "https://platetag.app/share/session/{$existing->token}",
                'deep_link'  => "platetag://share/session/{$existing->token}",
                'expires_at' => $existing->expires_at->toISOString(),
            ]);
        }

        $token = Str::random(48);

        SessionShareToken::create([
            'session_id' => $id,
            'created_by' => $user->id,
            'token'      => $token,
            'expires_at' => now()->addHours(self::TOKEN_TTL_HOURS),
        ]);

        return response()->json([
            'token'      => $token,
            'link'       => "https://platetag.app/share/session/{$token}",
            'deep_link'  => "platetag://share/session/{$token}",
            'expires_at' => now()->addHours(self::TOKEN_TTL_HOURS)->toISOString(),
        ]);
    }

    /**
     * GET /api/v1/share/session/{token}
     * Public preview — no auth required.
     * Returns session name, sharer's first name, plate count, and up to 12 plate thumbnails.
     * Geolocation is never included.
     */
    public function preview(string $token): JsonResponse
    {
        $record = SessionShareToken::query()
            ->where('token', $token)
            ->first();

        if (! $record) {
            return response()->json(['message' => 'Share link not found.'], 404);
        }

        if ($record->isExpired()) {
            return response()->json(['message' => 'This share link has expired.', 'expired' => true], 410);
        }

        $session = DB::table('discovery_sessions')
            ->where('id', $record->session_id)
            ->first();

        if (! $session) {
            return response()->json(['message' => 'This session no longer exists.'], 404);
        }

        $sharer = DB::table('users')->where('id', $record->created_by)->first();
        $sharerName = $sharer ? explode(' ', trim($sharer->name))[0] : 'Someone';

        // Total distinct plate count
        $plateCount = DB::table('user_discovered_plates')
            ->where('user_id', $record->created_by)
            ->where('session_id', $record->session_id)
            ->distinct('plate_id')
            ->count('plate_id');

        // Up to 12 plate thumbnails for the preview card — no geo data
        $plates = DB::table('user_discovered_plates as udp')
            ->join('plates', 'plates.id', '=', 'udp.plate_id')
            ->join('series', 'series.id', '=', 'plates.series_id')
            ->leftJoin('regions', 'regions.id', '=', 'series.region_id')
            ->where('udp.user_id', $record->created_by)
            ->where('udp.session_id', $record->session_id)
            ->groupBy('udp.plate_id', 'plates.name', 'series.name', 'series.country_code',
                      'regions.name', 'plates.image_filename')
            ->select([
                'udp.plate_id as id',
                'plates.name',
                'series.name as series_name',
                'series.country_code',
                'regions.name as region_name',
                'plates.image_filename',
            ])
            ->orderByRaw('MIN(udp.discovered_at) DESC')
            ->limit(12)
            ->get()
            ->map(fn ($p) => [
                'id'            => $p->id,
                'name'          => $p->name,
                'series_name'   => $p->series_name,
                'country_code'  => $p->country_code,
                'region_name'   => $p->region_name,
                'image_filename' => $p->image_filename,
            ]);

        return response()->json([
            'session_name'  => $session->name,
            'sharer_name'   => $sharerName,
            'plate_count'   => $plateCount,
            'expires_at'    => $record->expires_at->toISOString(),
            'plates'        => $plates,
        ]);
    }

    /**
     * POST /api/v1/share/session/{token}/claim
     * Authenticated — imports session plates into User B's collection.
     *
     * Audit requirements:
     *  - Geolocation is null-filled on all imported rows (never shared)
     *  - Duplicate detection per User B's existing collection
     *  - is_first_discovery computed accurately per User B
     *  - Self-claim is blocked
     */
    public function claim(Request $request, string $token): JsonResponse
    {
        $userB = $request->user();

        $record = SessionShareToken::query()
            ->where('token', $token)
            ->first();

        if (! $record) {
            return response()->json(['message' => 'Share link not found.'], 404);
        }

        if ($record->isExpired()) {
            return response()->json(['message' => 'This share link has expired.', 'expired' => true], 410);
        }

        // Block self-claim
        if ($record->created_by === $userB->id) {
            return response()->json(['message' => 'You cannot import your own session.'], 422);
        }

        // All distinct plate IDs from the shared session
        $sharedPlateIds = DB::table('user_discovered_plates')
            ->where('user_id', $record->created_by)
            ->where('session_id', $record->session_id)
            ->distinct()
            ->pluck('plate_id')
            ->all();

        if (empty($sharedPlateIds)) {
            return response()->json(['added' => 0, 'skipped' => 0]);
        }

        // Wrap in a transaction with a per-user advisory lock to prevent concurrent
        // double-import if User B taps the link twice simultaneously.
        $result = DB::transaction(function () use ($userB, $record, $sharedPlateIds) {
            // Lock this user's row to serialize concurrent claim attempts
            DB::table('users')->where('id', $userB->id)->lockForUpdate()->first();

            // Plates User B has already discovered (any session) — re-check inside lock
            $existingPlateIds = DB::table('user_discovered_plates')
                ->where('user_id', $userB->id)
                ->whereIn('plate_id', $sharedPlateIds)
                ->pluck('plate_id')
                ->flip()
                ->all();

            // User B's default session for the imported plates
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
                    // Geo is intentionally null — geolocation is never shared
                    'latitude'           => null,
                    'longitude'          => null,
                    'location_label'     => null,
                    'notes'              => null,
                    'created_at'         => $now,
                    'updated_at'         => $now,
                ];
            }

            // Enforce free-tier plate cap inside the lock so concurrent imports can't both
            // read "49 plates" and each add more, exceeding the limit.
            if (! $userB->is_premium && ! empty($rows)) {
                $currentCount = DB::table('user_discovered_plates')
                    ->where('user_id', $userB->id)
                    ->distinct('plate_id')
                    ->count('plate_id');
                $remainingSlots = max(0, 50 - $currentCount);
                if ($remainingSlots <= 0) {
                    return ['cap_reached' => true];
                }
                $rows = array_slice($rows, 0, $remainingSlots);
            }

            if (!empty($rows)) {
                DB::table('user_discovered_plates')->insert($rows);
            }

            return ['added' => count($rows), 'skipped' => count($sharedPlateIds) - count($rows)];
        });

        if (! empty($result['error'])) {
            return response()->json(['message' => 'Could not find your default collection. Please open the PlateTag app once to set it up.'], 422);
        }

        if (! empty($result['cap_reached'])) {
            return response()->json([
                'message' => 'Free plan plate limit reached. Upgrade to Full Access to import more plates.',
                'cap_reached' => true,
            ], 422);
        }

        return response()->json([
            'added'   => $result['added'],
            'skipped' => $result['skipped'],
        ]);
    }
}
