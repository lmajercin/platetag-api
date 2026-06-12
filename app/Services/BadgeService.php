<?php

namespace App\Services;

use App\Models\Badge;
use App\Models\Plate;
use App\Models\User;
use App\Models\UserBadge;
use Illuminate\Support\Carbon;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

class BadgeService
{
    /**
     * Check and award any badges earned after a new plate discovery.
     * Called from the discovery endpoint after the discovery row is saved.
     *
     * Returns a collection of newly awarded Badge models (empty if none earned).
     *
     * NOTE: This runs synchronously within the discovery request — acceptable at
     * beta scale. Flag for queued dispatch (CheckBadgeAwards job) before public launch
     * if latency becomes a concern on A2 Hosting shared hosting.
     */
    public function checkAfterDiscovery(User $user, Plate $plate): Collection
    {
        $newlyAwarded = collect();

        $newlyAwarded = $newlyAwarded->merge($this->checkGeographicBadges($user, $plate));
        $newlyAwarded = $newlyAwarded->merge($this->checkMilestoneBadges($user));
        $newlyAwarded = $newlyAwarded->merge($this->checkCollectionBadges($user, $plate));

        return $newlyAwarded;
    }

    // ── Geographic badges ────────────────────────────────────────────────────

    /**
     * Find all active geographic badges that include the region of the newly
     * discovered plate, then award any that the user has now fully completed.
     */
    private function checkGeographicBadges(User $user, Plate $plate): Collection
    {
        // Resolve the region of the discovered plate via plate → series → region.
        $regionId = DB::table('series')
            ->where('id', $plate->series_id)
            ->value('region_id');

        if (!$regionId) {
            return collect();
        }

        // Find active geographic badges that include this region and that the user
        // has not yet earned.
        $candidateBadgeIds = DB::table('badges')
            ->join('badge_regions', 'badges.id', '=', 'badge_regions.badge_id')
            ->where('badges.type', 'geographic')
            ->where('badges.is_active', true)       // Audit item #3: active filter
            ->where('badge_regions.region_id', $regionId)
            ->whereNotIn('badges.id', function ($q) use ($user) {
                $q->select('badge_id')
                  ->from('user_badges')
                  ->where('user_id', $user->id);
            })
            ->pluck('badges.id');

        if ($candidateBadgeIds->isEmpty()) {
            return collect();
        }

        // For each candidate badge, check if the user has discovered at least one
        // plate from every required region.
        $discovered = [];
        foreach ($candidateBadgeIds as $badgeId) {
            if ($this->userHasCompletedGeographicBadge($user->id, $badgeId)) {
                $discovered[] = $badgeId;
            }
        }

        if (empty($discovered)) {
            return collect();
        }

        return $this->awardBadges($user->id, $discovered);
    }

    /**
     * Returns true if the user has discovered at least one plate from every
     * region required by this geographic badge.
     */
    private function userHasCompletedGeographicBadge(int $userId, int $badgeId): bool
    {
        // Total regions required by this badge.
        $required = DB::table('badge_regions')
            ->where('badge_id', $badgeId)
            ->count();

        // Distinct regions the user has discovered among those required.
        $earned = DB::table('badge_regions')
            ->where('badge_regions.badge_id', $badgeId)
            ->whereExists(function ($q) use ($userId) {
                $q->select(DB::raw(1))
                  ->from('user_discovered_plates as udp')
                  ->join('plates', 'plates.id', '=', 'udp.plate_id')
                  ->join('series', 'series.id', '=', 'plates.series_id')
                  ->where('udp.user_id', $userId)
                  ->whereColumn('series.region_id', 'badge_regions.region_id');
            })
            ->count();

        return $earned >= $required;
    }

    // ── Collection badges ─────────────────────────────────────────────────────

    /**
     * Find all active collection badges that include the newly discovered plate,
     * then award any that the user has now fully completed.
     */
    private function checkCollectionBadges(User $user, Plate $plate): Collection
    {
        // Find active collection badges that include this plate and that the user
        // has not yet earned.
        $candidateBadgeIds = DB::table('badges')
            ->join('badge_plates', 'badges.id', '=', 'badge_plates.badge_id')
            ->where('badges.type', 'collection')
            ->where('badges.is_active', true)
            ->where('badge_plates.plate_id', $plate->id)
            ->whereNotIn('badges.id', function ($q) use ($user) {
                $q->select('badge_id')
                  ->from('user_badges')
                  ->where('user_id', $user->id);
            })
            ->pluck('badges.id');

        if ($candidateBadgeIds->isEmpty()) {
            return collect();
        }

        $earned = [];
        foreach ($candidateBadgeIds as $badgeId) {
            if ($this->userHasCompletedCollectionBadge($user->id, $badgeId)) {
                $earned[] = $badgeId;
            }
        }

        if (empty($earned)) {
            return collect();
        }

        return $this->awardBadges($user->id, $earned);
    }

    /**
     * Returns true if the user has discovered every plate required by this
     * collection badge.
     */
    private function userHasCompletedCollectionBadge(int $userId, int $badgeId): bool
    {
        $required = DB::table('badge_plates')
            ->where('badge_id', $badgeId)
            ->count();

        $collected = DB::table('badge_plates')
            ->where('badge_plates.badge_id', $badgeId)
            ->whereExists(function ($q) use ($userId) {
                $q->select(DB::raw(1))
                  ->from('user_discovered_plates as udp')
                  ->where('udp.user_id', $userId)
                  ->whereColumn('udp.plate_id', 'badge_plates.plate_id');
            })
            ->count();

        return $collected >= $required;
    }

    // ── Milestone badges ─────────────────────────────────────────────────────

    /**
     * Check all active milestone badges. Award any whose threshold the user
     * has now met or exceeded and has not yet earned.
     */
    private function checkMilestoneBadges(User $user): Collection
    {
        // Count the user's total first-discovery plates.
        $totalPlates = DB::table('user_discovered_plates')
            ->where('user_id', $user->id)
            ->where('is_first_discovery', true)
            ->count();

        // Find active milestone badges at or below the user's total that they
        // haven't earned yet.
        $eligibleIds = DB::table('badges')
            ->where('type', 'milestone')
            ->where('is_active', true)              // Audit item #3: active filter
            ->where('threshold', '<=', $totalPlates)
            ->whereNotIn('id', function ($q) use ($user) {
                $q->select('badge_id')
                  ->from('user_badges')
                  ->where('user_id', $user->id);
            })
            ->pluck('id')
            ->all();

        if (empty($eligibleIds)) {
            return collect();
        }

        return $this->awardBadges($user->id, $eligibleIds);
    }

    // ── Award helper ─────────────────────────────────────────────────────────

    /**
     * Insert user_badges rows for the given badge IDs.
     * Uses insertOrIgnore to handle the rare race condition where two concurrent
     * discovery requests both pass the "not yet awarded" check (Audit item #1).
     * The unique constraint on (user_id, badge_id) is the hard backstop.
     *
     * Returns the Badge models that were actually inserted (not already present).
     */
    private function awardBadges(int $userId, array $badgeIds): Collection
    {
        $now  = Carbon::now();
        $rows = array_map(fn($id) => [
            'user_id'    => $userId,
            'badge_id'   => $id,
            'awarded_at' => $now,
        ], $badgeIds);

        // insertOrIgnore: silently skips rows that violate the unique constraint.
        DB::table('user_badges')->insertOrIgnore($rows);

        // Return only the badges that are now present in user_badges (i.e., newly
        // inserted). In the race condition case, the second thread inserts 0 rows
        // and returns an empty collection — the user sees no duplicate popup.
        return Badge::whereIn('id', $badgeIds)->get();
    }
}
