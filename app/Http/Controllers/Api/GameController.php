<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Game;
use App\Models\Group;
use App\Models\GroupMember;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class GameController extends Controller
{
    // ─── index ─────────────────────────────────────────────────────────────────

    /**
     * List all games for a group.
     */
    public function index(Request $request, int $groupId): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->is_private && !$this->isMember($groupId, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        $games = Game::where('group_id', $groupId)
            ->with('winner:id,name')
            ->orderByDesc('created_at')
            ->get();

        return response()->json($games);
    }

    // ─── show ──────────────────────────────────────────────────────────────────

    /**
     * Show a single game.
     */
    public function show(Request $request, int $groupId, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->is_private && !$this->isMember($groupId, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        $game = Game::where('group_id', $groupId)->findOrFail($id);

        return response()->json($game->load('winner:id,name'));
    }

    // ─── store ─────────────────────────────────────────────────────────────────

    /**
     * Start a new game for the group (leader only).
     * type = '50_states' is the only active type in Build 87a.
     * 'road_rally' is valid in the DB but requires Build 87b UI.
     */
    public function store(Request $request, int $groupId): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can start a game.'], 403);
        }

        $validated = $request->validate([
            'type'    => ['required', 'in:50_states,road_rally'],
            'country' => ['nullable', 'in:US,CA'],
        ]);

        $country     = $validated['country'] ?? $group->country;
        $targetCount = $country === 'CA' ? 13 : 50;

        $game = Game::create([
            'group_id'     => $groupId,
            'type'         => $validated['type'],
            'country'      => $country,
            'status'       => 'active',
            'target_count' => $targetCount,
            'started_at'   => now(),
        ]);

        return response()->json($game, 201);
    }

    // ─── update ────────────────────────────────────────────────────────────────

    /**
     * Update a game — mark as completed, assign winner (leader only).
     */
    public function update(Request $request, int $groupId, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can update a game.'], 403);
        }

        $game = Game::where('group_id', $groupId)->findOrFail($id);

        $validated = $request->validate([
            'status'    => ['sometimes', 'in:active,completed'],
            'winner_id' => ['nullable', 'integer', 'exists:users,id'],
        ]);

        // Auto-stamp completed_at when transitioning to completed
        if (isset($validated['status']) && $validated['status'] === 'completed' && !$game->completed_at) {
            $validated['completed_at'] = now();
        }

        $game->update($validated);

        return response()->json($game->load('winner:id,name'));
    }

    // ─── Private Helper ────────────────────────────────────────────────────────

    private function isMember(int $groupId, int $userId): bool
    {
        return GroupMember::where('group_id', $groupId)->where('user_id', $userId)->exists();
    }
}
