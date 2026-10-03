<?php

namespace App\Filament\Pages;

use App\Models\GeoUsageSnapshot;
use Filament\Pages\Page;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;

class DiscoveryInsights extends Page
{
    protected static ?string $navigationIcon = 'heroicon-o-sparkles';

    protected static ?string $navigationGroup = 'Analytics';

    protected static ?string $navigationLabel = 'Discovery Insights';

    protected static ?int $navigationSort = 1;

    protected static string $view = 'filament.pages.discovery-insights';

    public int $days = 30;

    /** Lifetime KPIs */
    public int $totalDiscoveries = 0;

    public int $discoveriesWithLocation = 0;

    public int $discoveriesWithoutLocation = 0;

    public float $pctDiscoveriesWithLocation = 0;

    public int $activeCollectors = 0;

    public int $usersEverWithLocation = 0;

    public int $usersNeverWithLocation = 0;

    public float $pctUsersWithLocation = 0;

    /** @var list<array{label: string, count: int, pct: float}> */
    public array $byWeekday = [];

    /** @var list<array{hour: int, label: string, count: int, pct: float}> */
    public array $byHour = [];

    /** @var list<array<string, mixed>> */
    public array $regionalHotspots = [];

    /** @var list<array<string, mixed>> */
    public array $locationLabelHotspots = [];

    /** @var list<array<string, mixed>> */
    public array $geoSnapshots = [];

    public function mount(): void
    {
        $this->ensureSnapshotsExist();
        $this->loadReports();
    }

    public function setDays(int $days): void
    {
        if (! in_array($days, [30, 90], true)) {
            return;
        }

        $this->days = $days;
        $this->loadGeoSnapshots();
        $this->loadTimePatterns();
    }

    public function loadReports(): void
    {
        $this->loadLocationKpis();
        $this->loadTimePatterns();
        $this->loadRegionalHotspots();
        $this->loadGeoSnapshots();
    }

    protected function ensureSnapshotsExist(): void
    {
        if (GeoUsageSnapshot::query()->exists()) {
            return;
        }

        // First visit: backfill history so charts are useful immediately.
        Artisan::call('analytics:snapshot-geo', ['--backfill' => true]);
    }

    protected function loadLocationKpis(): void
    {
        $this->totalDiscoveries = (int) DB::table('user_discovered_plates')->count();
        $this->discoveriesWithLocation = (int) DB::table('user_discovered_plates')
            ->whereNotNull('latitude')
            ->whereNotNull('longitude')
            ->count();
        $this->discoveriesWithoutLocation = $this->totalDiscoveries - $this->discoveriesWithLocation;
        $this->pctDiscoveriesWithLocation = $this->totalDiscoveries > 0
            ? round(($this->discoveriesWithLocation / $this->totalDiscoveries) * 100, 1)
            : 0.0;

        $this->activeCollectors = (int) DB::table('user_discovered_plates')
            ->selectRaw('COUNT(DISTINCT user_id) as c')
            ->value('c');
        $this->usersEverWithLocation = (int) DB::table('user_discovered_plates')
            ->whereNotNull('latitude')
            ->whereNotNull('longitude')
            ->selectRaw('COUNT(DISTINCT user_id) as c')
            ->value('c');
        $this->usersNeverWithLocation = max(0, $this->activeCollectors - $this->usersEverWithLocation);
        $this->pctUsersWithLocation = $this->activeCollectors > 0
            ? round(($this->usersEverWithLocation / $this->activeCollectors) * 100, 1)
            : 0.0;
    }

    protected function loadTimePatterns(): void
    {
        $since = now()->subDays($this->days)->startOfDay();

        $weekdayRows = DB::table('user_discovered_plates')
            ->select(
                DB::raw('DAYOFWEEK(discovered_at) as dow'),
                DB::raw('COUNT(*) as discovery_count')
            )
            ->where('discovered_at', '>=', $since)
            ->groupBy('dow')
            ->pluck('discovery_count', 'dow');

        // MySQL DAYOFWEEK: 1=Sunday … 7=Saturday
        $labels = [
            2 => 'Mon', 3 => 'Tue', 4 => 'Wed', 5 => 'Thu',
            6 => 'Fri', 7 => 'Sat', 1 => 'Sun',
        ];
        $order = [2, 3, 4, 5, 6, 7, 1];
        $weekdayTotal = max(1, (int) $weekdayRows->sum());
        $this->byWeekday = [];
        foreach ($order as $dow) {
            $count = (int) ($weekdayRows[$dow] ?? 0);
            $this->byWeekday[] = [
                'label' => $labels[$dow],
                'count' => $count,
                'pct' => round(($count / $weekdayTotal) * 100, 1),
            ];
        }

        $hourRows = DB::table('user_discovered_plates')
            ->select(
                DB::raw('HOUR(discovered_at) as hour'),
                DB::raw('COUNT(*) as discovery_count')
            )
            ->where('discovered_at', '>=', $since)
            ->groupBy('hour')
            ->pluck('discovery_count', 'hour');

        $hourTotal = max(1, (int) $hourRows->sum());
        $this->byHour = [];
        for ($h = 0; $h < 24; $h++) {
            $count = (int) ($hourRows[$h] ?? 0);
            $this->byHour[] = [
                'hour' => $h,
                'label' => sprintf('%02d:00', $h),
                'count' => $count,
                'pct' => round(($count / $hourTotal) * 100, 1),
            ];
        }
    }

    protected function loadRegionalHotspots(): void
    {
        // Plate origin regions (catalog geography of the plate discovered)
        $this->regionalHotspots = DB::table('user_discovered_plates as udp')
            ->join('plates as p', 'udp.plate_id', '=', 'p.id')
            ->leftJoin('series as s', 'p.series_id', '=', 's.id')
            ->leftJoin('regions as r', 's.region_id', '=', 'r.id')
            ->select(
                DB::raw("COALESCE(r.name, 'Unknown') as region_name"),
                DB::raw("COALESCE(r.code, '—') as region_code"),
                DB::raw("COALESCE(s.country_code, '—') as country_code"),
                DB::raw('COUNT(*) as discovery_count')
            )
            ->groupBy('r.name', 'r.code', 's.country_code')
            ->orderByDesc('discovery_count')
            ->limit(20)
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();

        // Where users were when they logged (location_label from device)
        $this->locationLabelHotspots = DB::table('user_discovered_plates')
            ->select(
                'location_label',
                DB::raw('COUNT(*) as discovery_count')
            )
            ->whereNotNull('location_label')
            ->where('location_label', '!=', '')
            ->groupBy('location_label')
            ->orderByDesc('discovery_count')
            ->limit(20)
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadGeoSnapshots(): void
    {
        $since = now()->subDays($this->days)->startOfDay();

        $this->geoSnapshots = GeoUsageSnapshot::query()
            ->where('snapshot_date', '>=', $since)
            ->orderBy('snapshot_date')
            ->get()
            ->map(fn (GeoUsageSnapshot $s) => [
                'day' => $s->snapshot_date->toDateString(),
                'pct_discoveries' => $s->pct_discoveries_with_location,
                'pct_users' => $s->pct_users_with_location,
                'discoveries_total' => $s->discoveries_total,
                'active_users' => $s->active_users,
            ])
            ->all();
    }
}
