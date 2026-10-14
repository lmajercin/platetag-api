<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Game extends Model
{
    protected $fillable = [
        'group_id',
        'type',
        'country',
        'status',
        'winner_id',
        'winner_plates_user_id',
        'winner_states_user_id',
        'target_count',
        'start_date',
        'end_date',
        'started_at',
        'completed_at',
    ];

    protected function casts(): array
    {
        return [
            'start_date'   => 'date',
            'end_date'     => 'date',
            'started_at'   => 'datetime',
            'completed_at' => 'datetime',
        ];
    }

    // ─── Relationships ─────────────────────────────────────────────────────────

    public function group(): BelongsTo
    {
        return $this->belongsTo(Group::class);
    }

    /** Winner for 50 States games */
    public function winner(): BelongsTo
    {
        return $this->belongsTo(User::class, 'winner_id');
    }

    /** Road Rally: most unique plates winner */
    public function winnerPlates(): BelongsTo
    {
        return $this->belongsTo(User::class, 'winner_plates_user_id');
    }

    /** Road Rally: most states covered winner */
    public function winnerStates(): BelongsTo
    {
        return $this->belongsTo(User::class, 'winner_states_user_id');
    }

    // ─── Helpers ───────────────────────────────────────────────────────────────

    public function isActive(): bool
    {
        return $this->status === 'active';
    }

    public function isFiftyStates(): bool
    {
        return $this->type === '50_states';
    }

    public function isRoadRally(): bool
    {
        return $this->type === 'road_rally';
    }

    public function complete(?int $winnerId = null): void
    {
        $this->update([
            'status'       => 'completed',
            'winner_id'    => $winnerId,
            'completed_at' => now(),
        ]);
    }
}
