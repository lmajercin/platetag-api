<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Badge;
use App\Models\Game;
use App\Models\Group;
use App\Models\GroupMember;
use App\Models\UserBadge;
use Carbon\Carbon;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

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
            ->with([
                'winner:id,name',
                'winnerPlates:id,name',
                'winnerStates:id,name',
            ])
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

        return response()->json($game->load([
            'winner:id,name',
            'winnerPlates:id,name',
            'winnerStates:id,name',
        ]));
    }

    // ─── store ─────────────────────────────────────────────────────────────────

    /**
     * Start a new game for the group (leader only).
     * Branches to Road Rally or 50 States logic based on type.
     */
    public function store(Request $request, int $groupId): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can start a game.'], 403);
        }

        $validated = $request->validate([
            'type'       => ['required', 'in:50_states,road_rally'],
            'country'    => ['nullable', 'in:US,CA'],
            'start_date' => ['nullable', 'date', 'after_or_equal:today'],
            'end_date'   => [
                'nullable',
                'date',
                'after:start_date',
                'before_or_equal:' . now()->addDays(90)->toDateString(),
            ],
        ]);

        if ($validated['type'] === 'road_rally') {
            return $this->storeRoadRally($groupId, $group, $validated);
        }

        return $this->storeFiftyStates($groupId, $group, $validated);
    }

    // ─── update ────────────────────────────────────────────────────────────────

    /**
     * Update a game.
     * - Road Rally: edit end_date only (use /finalize to complete).
     * - 50 States: mark completed, assign winner (existing Build 87a behaviour).
     */
    public function update(Request $request, int $groupId, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can update a game.'], 403);
        }

        $game = Game::where('group_id', $groupId)->findOrFail($id);

        if ($game->type === 'road_rally') {
            return $this->updateRoadRallyEndDate($request, $game);
        }

        // ── 50 States: existing behaviour ──────────────────────────────────────
        $validated = $request->validate([
            'status'    => ['sometimes', 'in:active,completed'],
            'winner_id' => ['nullable', 'integer', 'exists:users,id'],
        ]);

        if (isset($validated['status']) && $validated['status'] === 'completed' && !$game->completed_at) {
            $validated['completed_at'] = now();
        }

        $game->update($validated);

        return response()->json($game->load('winner:id,name'));
    }

    // ─── finalize ──────────────────────────────────────────────────────────────

    /**
     * Finalize an active Road Rally.
     *
     * - Leader only.
     * - Uses DB transaction + lockForUpdate to prevent double-finalization.
     * - Winner calculation filters on created_at (server timestamp), never
     *   discovered_at (client-supplied — tamper risk — see @Audit GO 2026-10-13).
     * - Ex-members CAN win: no current-membership filter applied (policy 2026-10-13).
     * - Awards two distinct badges via firstOrCreate (idempotency).
     */
    public function finalize(Request $request, int $groupId, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($groupId);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can finalize a Road Rally.'], 403);
        }

        return DB::transaction(function () use ($groupId, $id) {

            $game = Game::where('group_id', $groupId)
                ->where('type', 'road_rally')
                ->lockForUpdate()
                ->findOrFail($id);

            // Guard: abort if already completed (prevents double-finalization)
            if ($game->status !== 'active') {
                return response()->json(['message' => 'This Road Rally has already been finalized.'], 409);
            }

            // Determine scoring window
            $start = $game->start_date
                ? Carbon::parse($game->start_date)->startOfDay()
                : Carbon::parse($game->started_at)->startOfDay();

            $end = $game->end_date
                ? Carbon::parse($game->end_date)->endOfDay()
                : now();

            // ── Winner: Most Unique Plates ─────────────────────────────────────
            // Uses created_at (server-set) — not discovered_at (client-set, tamper risk)
            $platesWinner = DB::table('group_discoveries')
                ->where('group_id', $groupId)
                ->whereBetween('created_at', [$start, $end])
                ->select('user_id', DB::raw('COUNT(DISTINCT plate_id) as plate_count'))
                ->groupBy('user_id')
                ->orderByDesc('plate_count')
                ->first();

            // ── Winner: Most States Covered ────────────────────────────────────
            // plates → series → regions join (plates have no direct region_id)
            $statesWinner = DB::table('group_discoveries as gd')
                ->join('plates',  'plates.id',  '=', 'gd.plate_id')
                ->join('series',  'series.id',  '=', 'plates.series_id')
                ->join('regions', 'regions.id', '=', 'series.region_id')
                ->where('gd.group_id', $groupId)
                ->whereBetween('gd.created_at', [$start, $end])
                ->select('gd.user_id', DB::raw('COUNT(DISTINCT regions.id) as state_count'))
                ->groupBy('gd.user_id')
                ->orderByDesc('state_count')
                ->first();

            // ── Mark game completed ────────────────────────────────────────────
            $game->update([
                'status'                 => 'completed',
                'winner_plates_user_id'  => $platesWinner?->user_id,
                'winner_states_user_id'  => $statesWinner?->user_id,
                'completed_at'           => now(),
            ]);

            // ── Award badges (firstOrCreate ensures idempotency) ───────────────
            $platesBadge = Badge::where('slug', 'road_rally_most_plates')->first();
            $statesBadge = Badge::where('slug', 'road_rally_most_states')->first();

            if ($platesWinner && $platesBadge) {
                UserBadge::firstOrCreate(
                    ['user_id' => $platesWinner->user_id, 'badge_id' => $platesBadge->id],
                    ['awarded_at' => now()]
                );
            }

            if ($statesWinner && $statesBadge) {
                UserBadge::firstOrCreate(
                    ['user_id' => $statesWinner->user_id, 'badge_id' => $statesBadge->id],
                    ['awarded_at' => now()]
                );
            }

            return response()->json($game->load([
                'winnerPlates:id,name',
                'winnerStates:id,name',
            ]));
        });
    }

    // ─── Private: store helpers ────────────────────────────────────────────────

    /**
     * Create a Road Rally game.
     * Uses a transaction + lockForUpdate to prevent duplicate active Road Rallies
     * from concurrent requests (@Audit condition 2026-10-13).
     */
    private function storeRoadRally(int $groupId, Group $group, array $validated): JsonResponse
    {
        return DB::transaction(function () use ($groupId, $group, $validated) {

            // Lock check: one active Road Rally per group at a time
            $existing = Game::where('group_id', $groupId)
                ->where('type', 'road_rally')
                ->where('status', 'active')
                ->lockForUpdate()
                ->first();

            if ($existing) {
                return response()->json([
                    'message' => 'There is already an active Road Rally for this group.',
                ], 409);
            }

            $game = Game::create([
                'group_id'   => $groupId,
                'type'       => 'road_rally',
                'country'    => $validated['country'] ?? $group->country,
                'status'     => 'active',
                'target_count' => 0,  // Road Rally has no fixed target
                'start_date' => $validated['start_date'] ?? now()->toDateString(),
                'end_date'   => $validated['end_date'] ?? null,
                'started_at' => now(),
            ]);

            return response()->json($game, 201);
        });
    }

    /**
     * Create a 50 States game (original Build 87a logic).
     */
    private function storeFiftyStates(int $groupId, Group $group, array $validated): JsonResponse
    {
        $country     = $validated['country'] ?? $group->country;
        $targetCount = $country === 'CA' ? 13 : 50;

        $game = Game::create([
            'group_id'     => $groupId,
            'type'         => '50_states',
            'country'      => $country,
            'status'       => 'active',
            'target_count' => $targetCount,
            'started_at'   => now(),
        ]);

        return response()->json($game, 201);
    }

    /**
     * Edit the end_date of an active Road Rally (leader only).
     * Clearing end_date makes the rally open-ended.
     * Status must be 'active' — completed rallies cannot be edited.
     */
    private function updateRoadRallyEndDate(Request $request, Game $game): JsonResponse
    {
        if ($game->status !== 'active') {
            return response()->json(['message' => 'Cannot edit a completed Road Rally.'], 409);
        }

        $validated = $request->validate([
            'end_date' => [
                'nullable',
                'date',
                'after:' . ($game->start_date?->toDateString() ?? 'today'),
                'before_or_equal:' . now()->addDays(90)->toDateString(),
            ],
        ]);

        $game->update(['end_date' => $validated['end_date']]);

        return response()->json($game->load([
            'winnerPlates:id,name',
            'winnerStates:id,name',
        ]));
    }

    // ─── Private helper ────────────────────────────────────────────────────────

    private function isMember(int $groupId, int $userId): bool
    {
        return GroupMember::where('group_id', $groupId)->where('user_id', $userId)->exists();
    }
}
