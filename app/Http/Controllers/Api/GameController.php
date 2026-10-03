<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Game;
use App\Models\Group;
use App\Models\GroupDiscovery;
use App\Models\GroupMember;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class GameController extends Controller
{
    /**
     * Get all games for a group.
     */
    public function index(Request $request, int $groupId): JsonResponse
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
        
        $games = Game::where('group_id', $groupId)
            ->with(['winner:id,name'])
            ->orderByDesc('created_at')
            ->get()
            ->map(function ($game) {
                return [
                    'id' => $game->id,
                    'game_type' => $game->game_type,
                    'target_count' => $game->target_count,
                    'country' => $game->country,
                    'status' => $game->status,
                    'winner' => $game->winner,
                    'start_date' => $game->start_date,
                    'end_date' => $game->end_date,
                    'created_at' => $game->created_at,
                    'completed_at' => $game->completed_at,
                ];
            });
        
        return response()->json(['games' => $games]);
    }

    /**
     * Get a specific game with standings.
     */
    public function show(Request $request, int $groupId, int $gameId): JsonResponse
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
        
        $game = Game::where('id', $gameId)
            ->where('group_id', $groupId)
            ->with(['winner:id,name'])
            ->first();
        
        if (!$game) {
            return response()->json(['message' => 'Game not found.'], 404);
        }
        
        // Calculate current standings
        $standings = $this->calculateGameStandings($groupId, $game);
        
        return response()->json([
            'game' => [
                'id' => $game->id,
                'game_type' => $game->game_type,
                'target_count' => $game->target_count,
                'country' => $game->country,
                'status' => $game->status,
                'winner' => $game->winner,
                'start_date' => $game->start_date,
                'end_date' => $game->end_date,
                'created_at' => $game->created_at,
                'completed_at' => $game->completed_at,
            ],
            'standings' => $standings,
        ]);
    }

    /**
     * Create a new game (leader only).
     */
    public function store(Request $request, int $groupId): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::where('id', $groupId)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        $data = $request->validate([
            'game_type' => ['required', 'string', 'in:50_states'],
            'country' => ['required', 'string', 'in:US,CA'],
            'start_date' => ['sometimes', 'date'],
            'end_date' => ['sometimes', 'date', 'after:start_date'],
        ]);
        
        // Set target based on country
        $targetCount = $data['country'] === 'US' ? 50 : 13;
        
        $game = Game::create([
            'group_id' => $groupId,
            'game_type' => $data['game_type'],
            'target_count' => $targetCount,
            'country' => $data['country'],
            'start_date' => $data['start_date'] ?? null,
            'end_date' => $data['end_date'] ?? null,
            'status' => 'active',
        ]);
        
        return response()->json([
            'game' => $game,
            'message' => 'Game created successfully.',
        ], 201);
    }

    /**
     * Update a game (leader only).
     */
    public function update(Request $request, int $groupId, int $gameId): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::where('id', $groupId)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        $game = Game::where('id', $gameId)
            ->where('group_id', $groupId)
            ->first();
        
        if (!$game) {
            return response()->json(['message' => 'Game not found.'], 404);
        }
        
        $data = $request->validate([
            'end_date' => ['sometimes', 'date', 'after_or_equal:today'],
        ]);
        
        $game->update($data);
        
        return response()->json([
            'game' => $game,
            'message' => 'Game updated successfully.',
        ]);
    }

    /**
     * Check and update game winners (called after discoveries).
     */
    public function checkWinners(int $groupId, int $gameId): void
    {
        $game = Game::where('id', $gameId)
            ->where('group_id', $groupId)
            ->where('status', 'active')
            ->first();
        
        if (!$game) {
            return;
        }
        
        $standings = $this->calculateGameStandings($groupId, $game);
        
        // Check if anyone reached the target
        $winner = collect($standings)->first(function ($standing) use ($game) {
            return $standing['state_points'] >= $game->target_count;
        });
        
        if ($winner) {
            $game->complete($winner['user_id']);
            // TODO: Award badges here (Build 87a badge system)
        }
    }

    /**
     * Calculate game standings.
     */
    private function calculateGameStandings(int $groupId, Game $game): array
    {
        // Get state points for each user
        $statePoints = GroupDiscovery::where('group_id', $groupId)
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
        $members = GroupMember::where('group_id', $groupId)
            ->with(['user:id,name'])
            ->get()
            ->keyBy('user_id');
        
        return $statePoints->map(function ($row, $index) use ($members, $game) {
            $member = $members[$row->user_id] ?? null;
            return [
                'rank' => $index + 1,
                'user_id' => $row->user_id,
                'user_name' => $member?->user->name,
                'member_color' => $member?->member_color,
                'state_points' => $row->state_points,
                'progress' => "{$row->state_points}/{$game->target_count}",
            ];
        })->values()->toArray();
    }
}
