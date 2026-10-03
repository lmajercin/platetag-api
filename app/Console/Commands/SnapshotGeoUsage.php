<?php

namespace App\Console\Commands;

use App\Models\GeoUsageSnapshot;
use Carbon\Carbon;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class SnapshotGeoUsage extends Command
{
    protected $signature = 'analytics:snapshot-geo
                            {--date= : Snapshot a specific date (Y-m-d). Default: yesterday}
                            {--backfill : Rebuild daily snapshots from first discovery through yesterday}';

    protected $description = 'Store a daily snapshot of discovery geolocation attachment rates for Usage Analytics charts.';

    public function handle(): int
    {
        if ($this->option('backfill')) {
            return $this->backfill();
        }

        $date = $this->option('date')
            ? Carbon::parse($this->option('date'))->startOfDay()
            : now()->subDay()->startOfDay();

        $this->writeSnapshot($date);
        $this->info('Geo usage snapshot saved for '.$date->toDateString());

        return self::SUCCESS;
    }

    protected function backfill(): int
    {
        $first = DB::table('user_discovered_plates')->min('discovered_at');
        if (! $first) {
            $this->warn('No discoveries found — nothing to backfill.');

            return self::SUCCESS;
        }

        $start = Carbon::parse($first)->startOfDay();
        $end = now()->subDay()->startOfDay();
        $written = 0;

        for ($day = $start->copy(); $day->lte($end); $day->addDay()) {
            $this->writeSnapshot($day);
            $written++;
        }

        $this->info("Backfilled {$written} daily geo usage snapshot(s).");

        return self::SUCCESS;
    }

    protected function writeSnapshot(Carbon $day): void
    {
        $start = $day->copy()->startOfDay();
        $end = $day->copy()->endOfDay();

        $total = (int) DB::table('user_discovered_plates')
            ->whereBetween('discovered_at', [$start, $end])
            ->count();
        $withLoc = (int) DB::table('user_discovered_plates')
            ->whereBetween('discovered_at', [$start, $end])
            ->whereNotNull('latitude')
            ->whereNotNull('longitude')
            ->count();
        $withoutLoc = $total - $withLoc;

        $activeUsers = (int) DB::table('user_discovered_plates')
            ->whereBetween('discovered_at', [$start, $end])
            ->selectRaw('COUNT(DISTINCT user_id) as c')
            ->value('c');

        $usersWithLoc = (int) DB::table('user_discovered_plates')
            ->whereBetween('discovered_at', [$start, $end])
            ->whereNotNull('latitude')
            ->whereNotNull('longitude')
            ->selectRaw('COUNT(DISTINCT user_id) as c')
            ->value('c');

        $usersWithoutLoc = max(0, $activeUsers - $usersWithLoc);

        $pctDisc = $total > 0 ? round(($withLoc / $total) * 100, 2) : 0;
        $pctUsers = $activeUsers > 0 ? round(($usersWithLoc / $activeUsers) * 100, 2) : 0;

        GeoUsageSnapshot::updateOrCreate(
            ['snapshot_date' => $start->toDateString()],
            [
                'discoveries_total' => $total,
                'discoveries_with_location' => $withLoc,
                'discoveries_without_location' => $withoutLoc,
                'active_users' => $activeUsers,
                'users_with_location' => $usersWithLoc,
                'users_without_location' => $usersWithoutLoc,
                'pct_discoveries_with_location' => $pctDisc,
                'pct_users_with_location' => $pctUsers,
            ]
        );
    }
}
