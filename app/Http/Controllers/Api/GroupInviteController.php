<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Group;
use App\Models\GroupMember;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class GroupInviteController extends Controller
{
    /**
     * Generate a new invite token (leader only).
     */
    public function generate(Request $request, int $id): JsonResponse
    {
        $user = $request->user();
        
        $group = Group::where('id', $id)
            ->where('leader_id', $user->id)
            ->first();
        
        if (!$group) {
            return response()->json(['message' => 'Group not found or you are not the leader.'], 403);
        }
        
        $data = $request->validate([
            'max_uses' => ['sometimes', 'integer', 'min:1', 'max:100'],
            'days_valid' => ['sometimes', 'integer', 'min:1', 'max:365'],
        ]);
        
        $maxUses = $data['max_uses'] ?? null;
        $daysValid = $data['days_valid'] ?? 30;
        
        // Generate new token (invalidates old one)
        $group->generateInviteToken($maxUses, $daysValid);
        
        return response()->json([
            'invite_token' => $group->invite_token,
            'invite_url' => url("/groups/join/{$group->invite_token}"),
            'expires_at' => $group->invite_expires_at,
            'max_uses' => $group->invite_max_uses,
            'message' => 'Invite token generated successfully.',
        ]);
    }

    /**
     * Preview a group before joining (via invite token).
     */
    public function preview(string $token): JsonResponse
    {
        $group = Group::where('invite_token', $token)
            ->with(['leader:id,name'])
            ->withCount('members')
            ->first();
        
        if (!$group) {
            return response()->json([
                'message' => 'This invite link is invalid.',
                'error_code' => 'INVITE_INVALID',
            ], 404);
        }
        
        if (!$group->isInviteTokenValid()) {
            $errorCode = 'INVITE_EXPIRED';
            $message = 'This invite link has expired. Please ask the group leader for a new link.';
            
            if ($group->invite_max_uses && $group->invite_token_uses >= $group->invite_max_uses) {
                $errorCode = 'INVITE_USED';
                $message = 'This invite link has already been used.';
            }
            
            return response()->json([
                'message' => $message,
                'error_code' => $errorCode,
            ], 410);
        }
        
        return response()->json([
            'group' => [
                'id' => $group->id,
                'name' => $group->name,
                'is_public' => $group->is_public,
                'leader' => $group->leader,
                'member_count' => $group->members_count,
                'member_cap' => $group->member_cap,
            ]
        ]);
    }

    /**
     * Join a group via invite token.
     */
    public function join(Request $request, string $token): JsonResponse
    {
        $user = $request->user();
        
        DB::beginTransaction();
        try {
            $group = Group::where('invite_token', $token)
                ->lockForUpdate()
                ->first();
            
            if (!$group) {
                DB::rollBack();
                return response()->json([
                    'message' => 'This invite link is invalid.',
                    'error_code' => 'INVITE_INVALID',
                ], 404);
            }
            
            // Check if token is valid
            if (!$group->isInviteTokenValid()) {
                DB::rollBack();
                
                $errorCode = 'INVITE_EXPIRED';
                $message = 'This invite link has expired. Please ask the group leader for a new link.';
                
                if ($group->invite_max_uses && $group->invite_token_uses >= $group->invite_max_uses) {
                    $errorCode = 'INVITE_USED';
                    $message = 'This invite link has already been used.';
                }
                
                return response()->json([
                    'message' => $message,
                    'error_code' => $errorCode,
                ], 410);
            }
            
            // Check if already a member
            $existingMember = GroupMember::where('group_id', $group->id)
                ->where('user_id', $user->id)
                ->exists();
            
            if ($existingMember) {
                DB::rollBack();
                return response()->json([
                    'message' => 'You are already a member of this group.',
                    'error_code' => 'ALREADY_MEMBER',
                ], 422);
            }
            
            // Check member cap
            if ($group->member_cap) {
                $currentCount = GroupMember::where('group_id', $group->id)->count();
                
                if ($currentCount >= $group->member_cap) {
                    DB::rollBack();
                    return response()->json([
                        'message' => 'This group is full.',
                        'error_code' => 'GROUP_FULL',
                    ], 422);
                }
            }
            
            // Add user to group
            $member = GroupMember::create([
                'group_id' => $group->id,
                'user_id' => $user->id,
                'joined_at' => now(),
            ]);
            
            // Assign color
            $member->assignColor();
            
            // Increment invite uses
            $group->incrementInviteUses();
            
            DB::commit();
            
            return response()->json([
                'group' => [
                    'id' => $group->id,
                    'name' => $group->name,
                    'is_public' => $group->is_public,
                    'member_color' => $member->member_color,
                ],
                'message' => 'Joined group successfully.',
            ]);
            
        } catch (\Exception $e) {
            DB::rollBack();
            return response()->json(['message' => 'Failed to join group.'], 500);
        }
    }
}
