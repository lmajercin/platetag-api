<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Group;
use App\Models\GroupMember;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

class GroupController extends Controller
{
    /**
     * Get all groups for the authenticated user.
     */
    public function index(Request $request): JsonResponse
    {
        $user = $request->user();
        
        // Get user's groups (both led and member of)
        $groups = Group::whereHas('members', function ($query) use ($user) {
            $query->where('user_id', $user->id);
        })
        ->orWhere('leader_id', $user->id)
        ->withCount('members')
        ->with(['leader:id,name'])
        ->get()
        ->map(function ($group) use ($user) {
            return [
                'id' => $group->id,
                'name' => $group->name,
                'is_public' => $group->is_public,
                'leader' => $group->leader,
                'member_count' => $group->members_count,
                'is_leader' => $group->leader_id === $user->id,
                'game_mode' => $group->game_mode,
                'created_at' => $group->created_at,
            ];
        });
        
        return response()->json(['groups' => $groups]);
    }

    /**
     * Get a specific group.
     */
    public function show(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::with(['leader:id,name'])
            ->withCount('members')
            ->find($id);
        
        if (!$group) {
            return response()->json(['message' => 'Group not found.'], 404);
        }
        
        // Private groups: must be a member
        if (!$group->is_public) {
            $isMember = GroupMember::where('group_id', $id)
                ->where('user_id', $user->id)
                ->exists();
            
            if (!$isMember && $group->leader_id !== $user->id) {
                return response()->json(['message' => 'Group not found.'], 404); // Same error as non-existent
            }
        }
        
        return response()->json([
            'group' => [
                'id' => $group->id,
                'name' => $group->name,
                'is_public' => $group->is_public,
                'leader' => $group->leader,
                'member_count' => $group->members_count,
                'member_cap' => $group->member_cap,
                'is_leader' => $group->leader_id === $user->id,
                'game_mode' => $group->game_mode,
                'created_at' => $group->created_at,
            ]
        ]);
    }

    /**
     * Create a new group.
     */
    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'name' => ['required', 'string', 'max:100', 'regex:/^[a-zA-Z0-9\s\-_]+$/'],
            'is_public' => ['required', 'boolean'],
            'country' => ['required', 'string', 'in:US,CA'],
            'game_mode' => ['sometimes', 'string', 'in:lifetime,fresh_start'],
        ]);
        
        $user = $request->user();
        
        DB::beginTransaction();
        try {
            // Create the group
            $group = Group::create([
                'name' => $data['name'],
                'leader_id' => $user->id,
                'is_public' => $data['is_public'],
                'game_mode' => $data['game_mode'] ?? 'lifetime',
            ]);
            
            // Add the leader as a member
            $member = GroupMember::create([
                'group_id' => $group->id,
                'user_id' => $user->id,
                'joined_at' => now(),
            ]);
            
            // Assign color to the leader (first member)
            $member->assignColor();
            
            // Generate invite token
            $group->generateInviteToken();
            
            DB::commit();
            
            return response()->json([
                'group' => [
                    'id' => $group->id,
                    'name' => $group->name,
                    'is_public' => $group->is_public,
                    'leader_id' => $group->leader_id,
                    'game_mode' => $group->game_mode,
                    'invite_token' => $group->invite_token,
                ],
                'message' => 'Group created successfully.',
            ], 201);
            
        } catch (\Exception $e) {
            DB::rollBack();
            return response()->json(['message' => 'Failed to create group.'], 500);
        }
    }

    /**
     * Update a group (leader only).
     */
    public function update(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::where('id', $id)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        $data = $request->validate([
            'name' => ['sometimes', 'string', 'max:100', 'regex:/^[a-zA-Z0-9\s\-_]+$/'],
            'is_public' => ['sometimes', 'boolean'],
            'game_mode' => ['sometimes', 'string', 'in:lifetime,fresh_start'],
            'member_cap' => ['sometimes', 'integer', 'min:1', 'max:100'],
        ]);
        
        $group->update($data);
        
        return response()->json([
            'group' => $group,
            'message' => 'Group updated successfully.',
        ]);
    }

    /**
     * Delete a group (leader only, soft delete).
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::where('id', $id)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        $group->delete(); // Soft delete
        
        return response()->json(['message' => 'Group deleted successfully.']);
    }

    /**
     * Leave a group (any member).
     */
    public function leave(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::find($id);
        
        if (!$group) {
            return response()->json(['message' => 'Group not found.'], 404);
        }
        
        // Leader cannot leave their own group
        if ($group->leader_id === $user->id) {
            return response()->json(['message' => 'Group leader cannot leave. Transfer leadership or delete the group.'], 422);
        }
        
        $deleted = GroupMember::where('group_id', $id)
            ->where('user_id', $user->id)
            ->delete();
        
        if (!$deleted) {
            return response()->json(['message' => 'You are not a member of this group.'], 422);
        }
        
        return response()->json(['message' => 'Left group successfully.']);
    }

    /**
     * Transfer leadership (leader only).
     */
    public function transferLeadership(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $data = $request->validate([
            'new_leader_id' => ['required', 'integer', 'exists:users,id'],
        ]);
        
        $group = Group::where('id', $id)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        // Verify new leader is a member
        $isMember = GroupMember::where('group_id', $id)
            ->where('user_id', $data['new_leader_id'])
            ->exists();
        
        if (!$isMember) {
            return response()->json(['message' => 'New leader must be a current member of the group.'], 422);
        }
        
        $group->update(['leader_id' => $data['new_leader_id']]);
        
        return response()->json(['message' => 'Leadership transferred successfully.']);
    }

    /**
     * Remove a member (leader only).
     */
    public function removeMember(Request $request, int $groupId, int $userId): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::where('id', $groupId)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        // Cannot remove the leader
        if ($userId === $group->leader_id) {
            return response()->json(['message' => 'Cannot remove the group leader.'], 422);
        }
        
        $deleted = GroupMember::where('group_id', $groupId)
            ->where('user_id', $userId)
            ->delete();
        
        if (!$deleted) {
            return response()->json(['message' => 'User is not a member of this group.'], 422);
        }
        
        return response()->json(['message' => 'Member removed successfully.']);
    }

    /**
     * Get all members of a group.
     */
    public function members(Request $request, int $id): JsonResponse
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
        
        $members = GroupMember::where('group_id', $id)
            ->with(['user:id,name'])
            ->get()
            ->map(function ($member) {
                return [
                    'id' => $member->user->id,
                    'name' => $member->user->name,
                    'member_color' => $member->member_color,
                    'joined_at' => $member->joined_at,
                ];
            });
        
        return response()->json(['members' => $members]);
    }
}
