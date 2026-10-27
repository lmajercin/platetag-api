<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Game;
use App\Models\Group;
use App\Models\GroupDiscovery;
use App\Models\GroupMember;
use App\Models\Region;
use Carbon\Carbon;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class GroupLeaderboardController extends Controller
{
    // ─── index ─────────────────────────────────────────────────────────────────

    /**
     * Group leaderboard — ranked by unique plates discovered in this group.
     * Also returns state_points (distinct states/provinces covered per member).
     */
    public function index(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->is_private && !$this->isMember($id, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        // ── B-31: Rally plate-count window (@Audit GO 2026-10-27) ────────────────
        // Optional ?game_id= parameter. When present, restrict counts to plates
        // logged DURING the rally window only (created_at, never discovered_at —
        // discovered_at is client-supplied and tamper-accessible).
        // BOLA guard: game must belong to this group and be type road_rally.
        $window = null;
        if ($request->filled('game_id')) {
            $game = Game::where('id', $request->integer('game_id'))
                ->where('group_id', $id)
                ->where('type', 'road_rally')
                ->firstOrFail();

            $start = $game->start_date
                ? Carbon::parse($game->start_date)->startOfDay()
                : Carbon::parse($game->started_at)->startOfDay();
            $end   = $game->end_date
                ? Carbon::parse($game->end_date)->endOfDay()
                : now();

            $window = [$start, $end];
        }

        $members = GroupMember::where('group_id', $id)
            ->with('user:id,name')
            ->get()
            ->map(function ($member) use ($id, $group, $window) {
                // Unique plates for this member in this group (rally-windowed if applicable)
                $platesQuery = GroupDiscovery::where('group_id', $id)
                    ->where('user_id', $member->user_id);
                if ($window) {
                    $platesQuery->whereBetween('created_at', $window);
                }
                $uniquePlates = $platesQuery->count();

                // Distinct states/provinces covered for this group's country.
                // plates → series → regions (plates has no direct region_id).
                $stateQuery = GroupDiscovery::where('group_discoveries.group_id', $id)
                    ->where('group_discoveries.user_id', $member->user_id)
                    ->join('plates',   'plates.id',   '=', 'group_discoveries.plate_id')
                    ->join('series',   'series.id',   '=', 'plates.series_id')
                    ->join('regions',  'regions.id',  '=', 'series.region_id')
                    ->whereIn('regions.country_code', $group->country === 'both' ? ['US', 'CA'] : [$group->country]);
                if ($window) {
                    $stateQuery->whereBetween('group_discoveries.created_at', $window);
                }
                $statePoints = $stateQuery->distinct('regions.code')->count('regions.code');

                return [
                    'user_id'      => $member->user_id,
                    'name'         => $member->user->name,
                    'color'        => $member->color,
                    'is_leader'    => $member->user_id === $group->leader_id,
                    'unique_plates'=> $uniquePlates,
                    'state_points' => $statePoints,
                    'joined_at'    => $member->joined_at,
                ];
            })
            ->sortByDesc('unique_plates')
            ->values();

        return response()->json([
            'group_id'     => $id,
            'target_count' => match($group->country) { 'CA' => 13, 'both' => 63, default => 50 },
            'country'      => $group->country,
            'members'      => $members,
        ]);
    }

    // ─── memberPlates ──────────────────────────────────────────────────────────

    /**
     * All plates a specific member has attributed to this group.
     */
    public function memberPlates(Request $request, int $id, int $userId): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->is_private && !$this->isMember($id, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        $plates = GroupDiscovery::where('group_id', $id)
            ->where('user_id', $userId)
            ->with('plate')
            ->get()
            ->map(fn($d) => [
                'plate' => $d->plate ? [
                    'id'        => $d->plate->id,
                    'name'      => $d->plate->name,
                    'image_url' => $d->plate->image_url,
                ] : null,
                'discovered_at' => $d->discovered_at,
            ])
            ->filter(fn($entry) => $entry['plate'] !== null)
            ->values();

        return response()->json($plates);
    }

    // ─── stateMap ──────────────────────────────────────────────────────────────

    /**
     * State/province completion map for the 50 States Game.
     * Returns each region with which members have a plate from that state.
     */
    public function stateMap(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->is_private && !$this->isMember($id, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        // All regions for this group's country
        $countryCodes = $group->country === 'both' ? ['US', 'CA'] : [$group->country];
        $regions = Region::whereIn('country_code', $countryCodes)
            ->orderBy('name')
            ->get(['id', 'code', 'name']);

        // Which users have a plate from each region (via group_discoveries → plates → region)
        $stateMap = $regions->map(function ($region) use ($id) {
            // plates → series → regions (plates has no direct region_id).
            $discovererIds = DB::table('group_discoveries')
                ->join('plates',  'plates.id',  '=', 'group_discoveries.plate_id')
                ->join('series',  'series.id',  '=', 'plates.series_id')
                ->where('group_discoveries.group_id', $id)
                ->where('series.region_id', $region->id)
                ->distinct()
                ->pluck('group_discoveries.user_id');

            return [
                'region_id'    => $region->id,
                'code'         => $region->code,
                'name'         => $region->name,
                'is_covered'   => $discovererIds->isNotEmpty(),
                'covered_by'   => $discovererIds->values(),
            ];
        });

        $coveredCount = $stateMap->where('is_covered', true)->count();

        return response()->json([
            'group_id'      => $id,
            'country'       => $group->country,
            'target'        => match($group->country) { 'CA' => 13, 'both' => 63, default => 50 },
            'covered_count' => $coveredCount,
            'states'        => $stateMap->values(),
        ]);
    }

    // ─── Private Helper ────────────────────────────────────────────────────────

    private function isMember(int $groupId, int $userId): bool
    {
        return GroupMember::where('group_id', $groupId)->where('user_id', $userId)->exists();
    }
}
