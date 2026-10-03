<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class GroupMember extends Model
{
    public $timestamps = false; // Using joined_at instead

    protected $fillable = [
        'group_id',
        'user_id',
        'member_color',
        'joined_at',
    ];

    protected $casts = [
        'joined_at' => 'datetime',
    ];

    /**
     * Get the group this membership belongs to.
     */
    public function group(): BelongsTo
    {
        return $this->belongsTo(Group::class);
    }

    /**
     * Get the user for this membership.
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Assign a color to this member.
     * Colors cycle through 8 options.
     */
    public function assignColor(): void
    {
        $colors = ['red', 'blue', 'green', 'orange', 'purple', 'teal', 'pink', 'yellow'];
        
        // Get count of existing members in this group
        $existingCount = GroupMember::where('group_id', $this->group_id)
            ->where('id', '!=', $this->id)
            ->count();
        
        // Assign color based on position (cycles after 8)
        $colorIndex = $existingCount % count($colors);
        $this->member_color = $colors[$colorIndex];
        $this->save();
    }
}
