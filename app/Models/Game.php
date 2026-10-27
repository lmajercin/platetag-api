<?php

namespace App\Models;

use Carbon\Carbon;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Facades\DB;

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

    // ─── Road Rally finalization ────────────────────────────────────────────────

    /**
     * Finalize a Road Rally: calculate winners, award badges, mark completed.
     * Extracted from GameController so the Artisan command (rallies:finalize) can
     * call the same logic without an HTTP context (@Audit GO 2026-10-27).
     *
     * Caller is responsible for:
     *   - Verifying the game belongs to the right group (BOLA guard)
     *   - Wrapping in DB::transaction() with lockForUpdate() before calling this
     *   - Checking $game->status === 'active' before calling (prevent double-finalization)
     *
     * @return array{winner_plates_user_id: int|null, winner_states_user_id: int|null}
     */
    public function finalizeRally(): array
    {
        $groupId = $this->group_id;

        // Scoring window — mirror @Audit-approved logic from GameController::finalize()
        $start = $this->start_date
            ? Carbon::parse($this->start_date)->startOfDay()
            : Carbon::parse($this->started_at)->startOfDay();
        $end   = $this->end_date
            ? Carbon::parse($this->end_date)->endOfDay()
            : now();

        // Winner: Most Unique Plates (created_at — tamper-safe server timestamp)
        $platesWinner = DB::table('group_discoveries')
            ->where('group_id', $groupId)
            ->whereBetween('created_at', [$start, $end])
            ->select('user_id', DB::raw('COUNT(DISTINCT plate_id) as plate_count'))
            ->groupBy('user_id')
            ->orderByDesc('plate_count')
            ->first();

        // Winner: Most States Covered (plates → series → regions join)
        $statesWinner = DB::table('group_discoveries as gd')
            ->join('plates',  'plates.id',  '=', 'gd.plate_id')
            ->join('series',  'series.id',  '=', 'plates.series_id')
            ->join('regions', 'regions.id', '=', 'series.region_id')
            ->where('gd.group_id', $groupId)
            ->whereBetween('gd.created_at', [$start, $end])
            ->select('gd.user_id', DB::raw('COUNT(DISTINCT regions.id) as state_count'))
            ->groupBy('gd.user_id')
            ->orderByDesc('state_count')
            ->first();

        // Mark game completed
        $this->update([
            'status'                => 'completed',
            'winner_plates_user_id' => $platesWinner?->user_id,
            'winner_states_user_id' => $statesWinner?->user_id,
            'completed_at'          => now(),
        ]);

        // Award badges (firstOrCreate — idempotent)
        $platesBadge = \App\Models\Badge::where('slug', 'road_rally_most_plates')->first();
        $statesBadge = \App\Models\Badge::where('slug', 'road_rally_most_states')->first();

        if ($platesWinner && $platesBadge) {
            \App\Models\UserBadge::firstOrCreate(
                ['user_id' => $platesWinner->user_id, 'badge_id' => $platesBadge->id],
                ['awarded_at' => now()]
            );
        }
        if ($statesWinner && $statesBadge) {
            \App\Models\UserBadge::firstOrCreate(
                ['user_id' => $statesWinner->user_id, 'badge_id' => $statesBadge->id],
                ['awarded_at' => now()]
            );
        }

        return [
            'winner_plates_user_id' => $platesWinner?->user_id,
            'winner_states_user_id' => $statesWinner?->user_id,
        ];
    }
}
