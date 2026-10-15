<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Group;
use App\Models\GroupDiscovery;
use App\Models\GroupMember;
use App\Models\Region;
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

        $members = GroupMember::where('group_id', $id)
            ->with('user:id,name')
            ->get()
            ->map(function ($member) use ($id, $group) {
                // Total unique plates this member attributed to the group
                $uniquePlates = GroupDiscovery::where('group_id', $id)
                    ->where('user_id', $member->user_id)
                    ->count();

                // Distinct states/provinces covered for this group's country.
                // plates → series → regions (plates has no direct region_id).
                $statePoints = GroupDiscovery::where('group_discoveries.group_id', $id)
                    ->where('group_discoveries.user_id', $member->user_id)
                    ->join('plates',   'plates.id',   '=', 'group_discoveries.plate_id')
                    ->join('series',   'series.id',   '=', 'plates.series_id')
                    ->join('regions',  'regions.id',  '=', 'series.region_id')
                    ->where('regions.country_code', $group->country)
                    ->distinct('regions.code')
                    ->count('regions.code');

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
            'target_count' => $group->country === 'CA' ? 13 : 50,
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
        $regions = Region::where('country_code', $group->country)
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
            'target'        => $group->country === 'CA' ? 13 : 50,
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
