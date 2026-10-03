<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Game extends Model
{
    protected $fillable = [
        'group_id',
        'game_type',
        'target_count',
        'country',
        'start_date',
        'end_date',
        'winner_user_id',
        'status',
        'completed_at',
    ];

    protected $casts = [
        'start_date' => 'date',
        'end_date' => 'date',
        'completed_at' => 'datetime',
    ];

    /**
     * Get the group this game belongs to.
     */
    public function group(): BelongsTo
    {
        return $this->belongsTo(Group::class);
    }

    /**
     * Get the winner of the game.
     */
    public function winner(): BelongsTo
    {
        return $this->belongsTo(User::class, 'winner_user_id');
    }

    /**
     * Check if this is a 50 States game.
     */
    public function isFiftyStatesGame(): bool
    {
        return $this->game_type === '50_states';
    }

    /**
     * Mark the game as completed with a winner.
     */
    public function complete(int $winnerUserId): void
    {
        $this->update([
            'status' => 'completed',
            'winner_user_id' => $winnerUserId,
            'completed_at' => now(),
        ]);
    }

    /**
     * Check if the game is active.
     */
    public function isActive(): bool
    {
        return $this->status === 'active';
    }
}
