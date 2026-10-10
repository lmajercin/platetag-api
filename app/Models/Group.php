<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\SoftDeletes;

class Group extends Model
{
    use SoftDeletes;

    protected $fillable = [
        'name',
        'description',
        'leader_id',
        'is_private',
        'invite_token_private',
        'invite_token_public',
        'private_token_uses',
        'public_token_uses',
        'private_token_expires_at',
        'public_token_expires_at',
        'member_cap',
        'country',
    ];

    /**
     * Never serialize invite tokens or internal counters to JSON responses.
     * Tokens are only returned by GroupInviteController::generate() explicitly.
     */
    protected $hidden = [
        'invite_token_private',
        'invite_token_public',
        'private_token_uses',
        'public_token_uses',
        'private_token_expires_at',
        'public_token_expires_at',
    ];

    protected function casts(): array
    {
        return [
            'is_private'                => 'boolean',
            'private_token_expires_at'  => 'datetime',
            'public_token_expires_at'   => 'datetime',
        ];
    }

    // ─── Relationships ─────────────────────────────────────────────────────────

    public function leader(): BelongsTo
    {
        return $this->belongsTo(User::class, 'leader_id');
    }

    public function groupMembers(): HasMany
    {
        return $this->hasMany(GroupMember::class);
    }

    public function members(): BelongsToMany
    {
        return $this->belongsToMany(User::class, 'group_members')
            ->withPivot('color', 'joined_at')
            ->withTimestamps();
    }

    public function discoveries(): HasMany
    {
        return $this->hasMany(GroupDiscovery::class);
    }

    public function games(): HasMany
    {
        return $this->hasMany(Game::class);
    }

    // ─── Token Helpers ─────────────────────────────────────────────────────────

    /**
     * Generate a fresh 64-char hex token.
     */
    public static function generateToken(): string
    {
        return bin2hex(random_bytes(32));
    }

    /**
     * Find a group by either invite token (private or public).
     * Returns null if not found or token is invalid/expired/used.
     */
    public static function findByToken(string $token): ?self
    {
        return static::where('invite_token_private', $token)
            ->orWhere('invite_token_public', $token)
            ->first();
    }
}
