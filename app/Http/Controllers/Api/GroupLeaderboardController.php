<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Group;
use App\Models\GroupDiscovery;
use App\Models\GroupMember;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class GroupLeaderboardController extends Controller
{
    /**
     * Get leaderboard for a group.
     */
    public function index(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::find($id);
        
        if (!$group) {
            return response()->json(['message' => 'Group not found.'], 404);
        }
        
        // Private groups: must be a member
        if (!$group->is_public) {
            $isMember = GroupMember::where('group_id', $id)
                ->where('user_id', $user->id)
                ->exists();
            
            if (!$isMember && $group->leader_id !== $user->id) {
                return response()->json(['message' => 'Group not found.'], 404);
            }
        }
        
        $mode = $request->query('mode', 'lifetime'); // 'lifetime' or 'fresh_start'
        
        // Build base query for discoveries
        $baseQuery = GroupDiscovery::where('group_id', $id);
        
        // Fresh start: only count discoveries after user joined
        if ($mode === 'fresh_start') {
            $baseQuery->join('group_members', function ($join) use ($id) {
                $join->on('group_discoveries.user_id', '=', 'group_members.user_id')
                     ->where('group_members.group_id', '=', $id)
                     ->whereColumn('group_discoveries.discovered_at', '>=', 'group_members.joined_at');
            });
        }
        
        // Unique Plates Leaderboard
        $uniquePlatesLeaderboard = (clone $baseQuery)
            ->select('user_id', DB::raw('COUNT(DISTINCT plate_id) as unique_plates'))
            ->groupBy('user_id')
            ->orderByDesc('unique_plates')
            ->get();
        
        // State Points Leaderboard
        // Join with plates and series to get region_id
        $statePointsLeaderboard = (clone $baseQuery)
            ->join('plates', 'group_discoveries.plate_id', '=', 'plates.id')
            ->join('series', 'plates.series_id', '=', 'series.id')
            ->select(
                'group_discoveries.user_id',
                DB::raw('COUNT(DISTINCT series.region_id) as state_points')
            )
            ->groupBy('group_discoveries.user_id')
            ->orderByDesc('state_points')
            ->get();
        
        // Get member details
        $members = GroupMember::where('group_id', $id)
            ->with(['user:id,name'])
            ->get()
            ->keyBy('user_id');
        
        // Format unique plates leaderboard
        $uniquePlates = $uniquePlatesLeaderboard->map(function ($row, $index) use ($members) {
            $member = $members[$row->user_id] ?? null;
            return [
                'rank' => $index + 1,
                'user_id' => $row->user_id,
                'user_name' => $member?->user->name,
                'member_color' => $member?->member_color,
                'count' => $row->unique_plates,
            ];
        })->values();
        
        // Format state points leaderboard
        $statePoints = $statePointsLeaderboard->map(function ($row, $index) use ($members) {
            $member = $members[$row->user_id] ?? null;
            return [
                'rank' => $index + 1,
                'user_id' => $row->user_id,
                'user_name' => $member?->user->name,
                'member_color' => $member?->member_color,
                'count' => $row->state_points,
            ];
        })->values();
        
        return response()->json([
            'mode' => $mode,
            'leaderboards' => [
                'unique_plates' => $uniquePlates,
                'state_points' => $statePoints,
            ]
        ]);
    }

    /**
     * Get a member's plates in a group.
     */
    public function memberPlates(Request $request, int $groupId, int $userId): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::find($groupId);
        
        if (!$group) {
            return response()->json(['message' => 'Group not found.'], 404);
        }
        
        // Private groups: must be a member
        if (!$group->is_public) {
            $isMember = GroupMember::where('group_id', $groupId)
                ->where('user_id', $user->id)
                ->exists();
            
            if (!$isMember && $group->leader_id !== $user->id) {
                return response()->json(['message' => 'Group not found.'], 404);
            }
        }
        
        // Get member's discoveries
        $discoveries = GroupDiscovery::where('group_id', $groupId)
            ->where('user_id', $userId)
            ->with([
                'plate:id,name,image_filename',
                'plate.series:id,name,region_id',
                'plate.series.region:id,name,country_code',
            ])
            ->orderByDesc('discovered_at')
            ->paginate(50);
        
        $plates = $discoveries->map(function ($discovery) {
            return [
                'id' => $discovery->plate->id,
                'name' => $discovery->plate->name,
                'image_url' => $discovery->plate->image_filename 
                    ? url("storage/plates/{$discovery->plate->image_filename}")
                    : null,
                'series' => $discovery->plate->series?->name,
                'region' => $discovery->plate->series?->region?->name,
                'country_code' => $discovery->plate->series?->region?->country_code,
                'discovered_at' => $discovery->discovered_at,
            ];
        });
        
        return response()->json([
            'plates' => $plates,
            'pagination' => [
                'current_page' => $discoveries->currentPage(),
                'last_page' => $discoveries->lastPage(),
                'per_page' => $discoveries->perPage(),
                'total' => $discoveries->total(),
            ]
        ]);
    }

    /**
     * Get state fill map data for a group.
     */
    public function stateMap(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::find($id);
        
        if (!$group) {
            return response()->json(['message' => 'Group not found.'], 404);
        }
        
        // Private groups: must be a member
        if (!$group->is_public) {
            $isMember = GroupMember::where('group_id', $id)
                ->where('user_id', $user->id)
                ->exists();
            
            if (!$isMember && $group->leader_id !== $user->id) {
                return response()->json(['message' => 'Group not found.'], 404);
            }
        }
        
        // Get first discovery per region (state) per group
        $stateFirsts = GroupDiscovery::where('group_discoveries.group_id', $id)
            ->join('plates', 'group_discoveries.plate_id', '=', 'plates.id')
            ->join('series', 'plates.series_id', '=', 'series.id')
            ->join('group_members', function ($join) use ($id) {
                $join->on('group_discoveries.user_id', '=', 'group_members.user_id')
                     ->where('group_members.group_id', '=', $id);
            })
            ->join('users', 'group_discoveries.user_id', '=', 'users.id')
            ->select(
                'series.region_id',
                DB::raw('MIN(group_discoveries.discovered_at) as first_discovered_at'),
                DB::raw("(SELECT user_id FROM group_discoveries gd2 
                         JOIN plates p2 ON gd2.plate_id = p2.id
                         JOIN series s2 ON p2.series_id = s2.id
                         WHERE gd2.group_id = {$id}
                         AND s2.region_id = series.region_id
                         ORDER BY gd2.discovered_at ASC
                         LIMIT 1) as first_user_id"),
            )
            ->groupBy('series.region_id')
            ->get();
        
        // Get member colors
        $members = GroupMember::where('group_id', $id)
            ->with(['user:id,name'])
            ->get()
            ->keyBy('user_id');
        
        $stateMap = $stateFirsts->map(function ($row) use ($members) {
            $member = $members[$row->first_user_id] ?? null;
            return [
                'region_id' => $row->region_id,
                'user_id' => $row->first_user_id,
                'user_name' => $member?->user->name,
                'member_color' => $member?->member_color,
                'first_discovered_at' => $row->first_discovered_at,
            ];
        });
        
        return response()->json(['state_map' => $stateMap]);
    }
}
