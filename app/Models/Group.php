<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Support\Str;

class Group extends Model
{
    use SoftDeletes;

    protected $fillable = [
        'name',
        'leader_id',
        'is_public',
        'member_cap',
        'invite_token',
        'invite_token_uses',
        'invite_max_uses',
        'invite_expires_at',
        'game_mode',
    ];

    protected $casts = [
        'is_public' => 'boolean',
        'invite_expires_at' => 'datetime',
    ];

    /**
     * Get the leader of the group.
     */
    public function leader(): BelongsTo
    {
        return $this->belongsTo(User::class, 'leader_id');
    }

    /**
     * Get all members of the group.
     */
    public function members(): HasMany
    {
        return $this->hasMany(GroupMember::class);
    }

    /**
     * Get all discoveries made in this group.
     */
    public function discoveries(): HasMany
    {
        return $this->hasMany(GroupDiscovery::class);
    }

    /**
     * Get all games for this group.
     */
    public function games(): HasMany
    {
        return $this->hasMany(Game::class);
    }

    /**
     * Generate a new invite token for the group.
     */
    public function generateInviteToken(int $maxUses = null, int $daysValid = 30): void
    {
        $this->update([
            'invite_token' => Str::random(64),
            'invite_token_uses' => 0,
            'invite_max_uses' => $maxUses ?? ($this->is_public ? null : 1),
            'invite_expires_at' => now()->addDays($daysValid),
        ]);
    }

    /**
     * Check if the invite token is valid.
     */
    public function isInviteTokenValid(): bool
    {
        if (!$this->invite_token) {
            return false;
        }

        if ($this->invite_expires_at && $this->invite_expires_at->isPast()) {
            return false;
        }

        if ($this->invite_max_uses && $this->invite_token_uses >= $this->invite_max_uses) {
            return false;
        }

        return true;
    }

    /**
     * Increment the invite token usage count.
     */
    public function incrementInviteUses(): void
    {
        $this->increment('invite_token_uses');
    }
}
