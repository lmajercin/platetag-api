<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use App\Models\User;

class AwardRetroactiveBadges extends Command
{
    protected $signature   = 'badges:retroactive {--user= : Only process this user ID}';
    protected $description = 'Award badges retroactively based on each user\'s existing collection.';

    public function handle(): int
    {
        $userId = $this->option('user');

        $users = $userId
            ? User::where('id', $userId)->get()
            : User::all();

        if ($users->isEmpty()) {
            $this->error('No users found.');
            return 1;
        }

        // Load all active badges with their required region IDs
        $geoBadges       = DB::table('badges')
            ->where('type', 'geographic')
            ->where('is_active', true)
            ->get();

        $milestoneBadges = DB::table('badges')
            ->where('type', 'milestone')
            ->where('is_active', true)
            ->orderBy('threshold')
            ->get();

        $collectionBadges = DB::table('badges')
            ->where('type', 'collection')
            ->where('is_active', true)
            ->get();

        // Map badge_id → set of required region_ids
        $badgeRegionMap = [];
        $badgeRegionRows = DB::table('badge_regions')->get();
        foreach ($badgeRegionRows as $row) {
            $badgeRegionMap[$row->badge_id][] = $row->region_id;
        }

        // Map badge_id → set of required plate_ids
        $badgePlateMap = [];
        $badgePlateRows = DB::table('badge_plates')->get();
        foreach ($badgePlateRows as $row) {
            $badgePlateMap[$row->badge_id][] = $row->plate_id;
        }

        $totalAwarded = 0;
        $now          = now()->toDateTimeString();

        foreach ($users as $user) {
            // Regions this user has discovered at least one plate from
            $discoveredRegionIds = DB::table('user_discovered_plates as udp')
                ->join('plates', 'plates.id', '=', 'udp.plate_id')
                ->join('series', 'series.id', '=', 'plates.series_id')
                ->where('udp.user_id', $user->id)
                ->where('udp.is_first_discovery', true)
                ->whereNotNull('series.region_id')
                ->pluck('series.region_id')
                ->unique()
                ->flip() // turn into a set for O(1) lookup
                ->all();

            // Total unique plates (first discoveries)
            $totalPlates = DB::table('user_discovered_plates')
                ->where('user_id', $user->id)
                ->where('is_first_discovery', true)
                ->count();

            // Plate IDs this user has collected (for collection badges)
            $discoveredPlateIds = DB::table('user_discovered_plates')
                ->where('user_id', $user->id)
                ->pluck('plate_id')
                ->flip()
                ->all();

            // Already-earned badge IDs
            $alreadyEarned = DB::table('user_badges')
                ->where('user_id', $user->id)
                ->pluck('badge_id')
                ->flip()
                ->all();

            $toInsert = [];

            // ── Geographic badges ────────────────────────────────────────────
            foreach ($geoBadges as $badge) {
                if (isset($alreadyEarned[$badge->id])) continue;

                $required = $badgeRegionMap[$badge->id] ?? [];
                if (empty($required)) continue;

                $completed = true;
                foreach ($required as $regionId) {
                    if (!isset($discoveredRegionIds[$regionId])) {
                        $completed = false;
                        break;
                    }
                }

                if ($completed) {
                    $toInsert[] = [
                        'user_id'    => $user->id,
                        'badge_id'   => $badge->id,
                        'awarded_at' => $now,
                    ];
                }
            }

            // ── Milestone badges ─────────────────────────────────────────────
            foreach ($milestoneBadges as $badge) {
                if (isset($alreadyEarned[$badge->id])) continue;
                if ($totalPlates >= $badge->threshold) {
                    $toInsert[] = [
                        'user_id'    => $user->id,
                        'badge_id'   => $badge->id,
                        'awarded_at' => $now,
                    ];
                }
            }

            // ── Collection badges ────────────────────────────────────────────
            foreach ($collectionBadges as $badge) {
                if (isset($alreadyEarned[$badge->id])) continue;
                $required = $badgePlateMap[$badge->id] ?? [];
                if (empty($required)) continue;

                $completed = true;
                foreach ($required as $plateId) {
                    if (!isset($discoveredPlateIds[$plateId])) {
                        $completed = false;
                        break;
                    }
                }

                if ($completed) {
                    $toInsert[] = [
                        'user_id'    => $user->id,
                        'badge_id'   => $badge->id,
                        'awarded_at' => $now,
                    ];
                }
            }

            if (!empty($toInsert)) {
                DB::table('user_badges')->insertOrIgnore($toInsert);
                $count = count($toInsert);
                $totalAwarded += $count;
                $this->line("  User {$user->id} ({$user->email}): awarded {$count} badge(s).");
            }
        }

        $this->info("Done. {$totalAwarded} badge(s) awarded across {$users->count()} user(s).");
        return 0;
    }
}
