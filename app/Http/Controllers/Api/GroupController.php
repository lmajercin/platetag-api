<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Group;
use App\Models\GroupMember;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class GroupController extends Controller
{
    // ─── index ─────────────────────────────────────────────────────────────────

    /**
     * List all groups the authenticated user belongs to.
     */
    public function index(Request $request): JsonResponse
    {
        $user = $request->user();

        $groups = $user->groups()
            ->with('leader:id,name')
            ->withCount('members')
            ->get()
            ->map(function ($group) use ($user) {
                $group->is_leader = $group->leader_id === $user->id;
                $group->member_color = $group->pivot->color;
                return $group;
            });

        return response()->json($groups);
    }

    // ─── show ──────────────────────────────────────────────────────────────────

    /**
     * Show a group's detail. Private groups are 404 to non-members.
     */
    public function show(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->is_private && !$this->isMember($group->id, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        $group->load(['leader:id,name', 'groupMembers.user:id,name', 'games']);
        $group->loadCount('members');
        $group->is_leader    = $group->leader_id === $user->id;
        $group->member_color = GroupMember::where('group_id', $id)->where('user_id', $user->id)->value('color');

        return response()->json($group);
    }

    // ─── store ─────────────────────────────────────────────────────────────────

    /**
     * Create a new group. Creator becomes leader and is auto-enrolled as first member.
     */
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'name'        => ['required', 'string', 'max:255'],
            'description' => ['nullable', 'string', 'max:1000'],
            'is_private'  => ['boolean'],
            'member_cap'  => ['nullable', 'integer', 'min:2', 'max:100'],
            'country'     => ['nullable', 'in:US,CA,both'],
        ]);

        $user = $request->user();

        $group = Group::create(array_merge($validated, [
            'leader_id' => $user->id,
            'country'   => $validated['country'] ?? 'US',
        ]));

        // Leader auto-joins as the first member with the first color
        GroupMember::create([
            'group_id'  => $group->id,
            'user_id'   => $user->id,
            'color'     => GroupMember::COLORS[0],
            'joined_at' => now(),
        ]);

        return response()->json($group->load('leader:id,name'), 201);
    }

    // ─── update ────────────────────────────────────────────────────────────────

    /**
     * Update group metadata (leader only).
     */
    public function update(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can update this group.'], 403);
        }

        $validated = $request->validate([
            'name'        => ['sometimes', 'string', 'max:255'],
            'description' => ['nullable', 'string', 'max:1000'],
            'is_private'  => ['boolean'],
            'member_cap'  => ['nullable', 'integer', 'min:2', 'max:100'],
        ]);

        $group->update($validated);

        return response()->json($group->load('leader:id,name'));
    }

    // ─── destroy ───────────────────────────────────────────────────────────────

    /**
     * Soft-delete a group (leader only).
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can delete this group.'], 403);
        }

        $group->delete();

        return response()->json(['message' => 'Group deleted.']);
    }

    // ─── leave ─────────────────────────────────────────────────────────────────

    /**
     * Leave a group. The leader must transfer leadership first.
     */
    public function leave(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->leader_id === $user->id) {
            return response()->json([
                'message' => 'You are the leader. Transfer leadership before leaving, or delete the group.',
            ], 422);
        }

        GroupMember::where('group_id', $id)->where('user_id', $user->id)->delete();

        return response()->json(['message' => 'You have left the group.']);
    }

    // ─── transferLeadership ────────────────────────────────────────────────────

    /**
     * Transfer leadership to another member (current leader only).
     */
    public function transferLeadership(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can transfer leadership.'], 403);
        }

        $validated = $request->validate([
            'user_id' => ['required', 'integer'],
        ]);

        if (!$this->isMember($id, $validated['user_id'])) {
            return response()->json(['message' => 'That user is not a member of this group.'], 422);
        }

        $group->update(['leader_id' => $validated['user_id']]);

        return response()->json($group->load('leader:id,name'));
    }

    // ─── removeMember ──────────────────────────────────────────────────────────

    /**
     * Remove a member from the group (leader only).
     */
    public function removeMember(Request $request, int $id, int $memberId): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can remove members.'], 403);
        }

        if ($memberId === $user->id) {
            return response()->json([
                'message' => 'Cannot remove yourself. Transfer leadership or delete the group.',
            ], 422);
        }

        GroupMember::where('group_id', $id)->where('user_id', $memberId)->delete();

        return response()->json(['message' => 'Member removed.']);
    }

    // ─── members ───────────────────────────────────────────────────────────────

    /**
     * List all members of a group.
     */
    public function members(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->is_private && !$this->isMember($id, $user->id)) {
            return response()->json(['message' => 'Not found.'], 404);
        }

        $members = GroupMember::where('group_id', $id)
            ->with('user:id,name')
            ->get()
            ->map(fn($m) => [
                'user_id'    => $m->user_id,
                'name'       => $m->user->name,
                'color'      => $m->color,
                'is_leader'  => $m->user_id === $group->leader_id,
                'joined_at'  => $m->joined_at,
            ]);

        return response()->json($members);
    }

    // ─── Private Helper ────────────────────────────────────────────────────────

    private function isMember(int $groupId, int $userId): bool
    {
        return GroupMember::where('group_id', $groupId)->where('user_id', $userId)->exists();
    }
}
