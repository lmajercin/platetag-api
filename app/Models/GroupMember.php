<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class GroupMember extends Model
{
    /**
     * The 8 available member colors (Design-approved Build 87a palette).
     */
    public const COLORS = [
        'red',
        'blue',
        'green',
        'orange',
        'purple',
        'teal',
        'pink',
        'yellow',
    ];

    protected $fillable = [
        'group_id',
        'user_id',
        'color',
        'joined_at',
    ];

    protected function casts(): array
    {
        return [
            'joined_at' => 'datetime',
        ];
    }

    // ─── Relationships ─────────────────────────────────────────────────────────

    public function group(): BelongsTo
    {
        return $this->belongsTo(Group::class);
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    // ─── Color Assignment ──────────────────────────────────────────────────────

    /**
     * Pick the next available color for a new member joining a group.
     * Returns the first unused color; wraps around if all 8 are taken.
     */
    public static function nextColor(int $groupId): string
    {
        $usedColors = static::where('group_id', $groupId)->pluck('color')->toArray();
        $available  = array_diff(self::COLORS, $usedColors);

        if (!empty($available)) {
            return array_values($available)[0];
        }

        // All 8 in use — wrap around based on member count
        $count = static::where('group_id', $groupId)->count();
        return self::COLORS[$count % count(self::COLORS)];
    }
}
