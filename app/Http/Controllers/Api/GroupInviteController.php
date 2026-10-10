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
    // ─── generate ──────────────────────────────────────────────────────────────

    /**
     * Generate a new invite token for a group (leader only).
     * type = 'private' (single-use) | 'public' (unlimited, 30-day expiry)
     */
    public function generate(Request $request, int $id): JsonResponse
    {
        $user  = $request->user();
        $group = Group::findOrFail($id);

        if ($group->leader_id !== $user->id) {
            return response()->json(['message' => 'Only the group leader can generate invite tokens.'], 403);
        }

        $validated = $request->validate([
            'type' => ['required', 'in:private,public'],
        ]);

        $token     = Group::generateToken();
        $expiresAt = now()->addDays(30);

        if ($validated['type'] === 'private') {
            $group->update([
                'invite_token_private'      => $token,
                'private_token_uses'        => 0,
                'private_token_expires_at'  => $expiresAt,
            ]);
        } else {
            $group->update([
                'invite_token_public'       => $token,
                'public_token_uses'         => 0,
                'public_token_expires_at'   => $expiresAt,
            ]);
        }

        return response()->json([
            'token'      => $token,
            'type'       => $validated['type'],
            'expires_at' => $expiresAt->toISOString(),
        ]);
    }

    // ─── preview ───────────────────────────────────────────────────────────────

    /**
     * Public — preview group info via invite token. No auth required.
     * Used for the join screen before the user taps "Join".
     */
    public function preview(string $token): JsonResponse
    {
        $group = Group::findByToken($token);

        if (!$group) {
            return response()->json(['message' => 'Invalid invite link.'], 404);
        }

        [$valid, $error] = $this->validateToken($group, $token);
        if (!$valid) {
            return response()->json(['message' => $error], 410);
        }

        return response()->json([
            'group_id'     => $group->id,
            'name'         => $group->name,
            'description'  => $group->description,
            'leader_name'  => $group->leader->name,
            'member_count' => $group->groupMembers()->count(),
            'member_cap'   => $group->member_cap,
            'country'      => $group->country,
        ]);
    }

    // ─── join ──────────────────────────────────────────────────────────────────

    /**
     * Join a group via invite token (auth required).
     * Atomic transaction — prevents double-join under concurrent requests.
     */
    public function join(Request $request, string $token): JsonResponse
    {
        $user = $request->user();

        $result = DB::transaction(function () use ($user, $token) {
            $group = Group::lockForUpdate()->findByToken($token);

            if (!$group) {
                return ['error' => 'Invalid invite link.', 'status' => 404];
            }

            [$valid, $error] = $this->validateToken($group, $token);
            if (!$valid) {
                return ['error' => $error, 'status' => 410];
            }

            // Already a member?
            $alreadyMember = GroupMember::where('group_id', $group->id)
                ->where('user_id', $user->id)
                ->lockForUpdate()
                ->exists();

            if ($alreadyMember) {
                return ['error' => 'You are already a member of this group.', 'status' => 422];
            }

            // Member cap check
            if ($group->member_cap !== null) {
                $currentCount = GroupMember::where('group_id', $group->id)->lockForUpdate()->count();
                if ($currentCount >= $group->member_cap) {
                    return ['error' => 'This group is full.', 'status' => 422];
                }
            }

            // Assign color
            $color = GroupMember::nextColor($group->id);

            GroupMember::create([
                'group_id'  => $group->id,
                'user_id'   => $user->id,
                'color'     => $color,
                'joined_at' => now(),
            ]);

            // Track token usage (private token becomes invalid after 1 use)
            $isPrivate = $group->invite_token_private === $token;
            if ($isPrivate) {
                $group->increment('private_token_uses');
            } else {
                $group->increment('public_token_uses');
            }

            return ['group' => $group->load('leader:id,name'), 'status' => 200];
        });

        if (isset($result['error'])) {
            return response()->json(['message' => $result['error']], $result['status']);
        }

        return response()->json($result['group']);
    }

    // ─── Private Helper ────────────────────────────────────────────────────────

    /**
     * Validate a token's expiry and single-use status.
     * Returns [bool $valid, string|null $errorMessage]
     */
    private function validateToken(Group $group, string $token): array
    {
        $isPrivate = $group->invite_token_private === $token;
        $expiresAt = $isPrivate ? $group->private_token_expires_at : $group->public_token_expires_at;

        if ($expiresAt && $expiresAt->isPast()) {
            return [false, 'This invite link has expired.'];
        }

        if ($isPrivate && $group->private_token_uses >= 1) {
            return [false, 'This invite link has already been used.'];
        }

        return [true, null];
    }
}
