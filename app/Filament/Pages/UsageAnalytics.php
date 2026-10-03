<?php

namespace App\Filament\Pages;

use Filament\Pages\Page;
use Illuminate\Support\Facades\DB;

class UsageAnalytics extends Page
{
    protected static ?string $navigationIcon = 'heroicon-o-table-cells';

    protected static ?string $navigationGroup = 'Analytics';

    protected static ?string $navigationLabel = 'Usage Reports';

    protected static ?int $navigationSort = 3;

    protected static string $view = 'filament.pages.usage-analytics';

    public int $days = 30;

    public int $usersDays = 30;

    public int $activeUsersDays = 30;

    /** @var list<array<string, mixed>> */
    public array $mostDiscoveredPlates = [];

    /** @var list<array<string, mixed>> */
    public array $postLaunchUsers = [];

    /** @var list<array<string, mixed>> */
    public array $uniquePlatesPerUser = [];

    /** @var list<array<string, mixed>> */
    public array $discoveriesPerUser = [];

    /** @var list<array<string, mixed>> */
    public array $platesPerSession = [];

    /** @var list<array<string, mixed>> */
    public array $discoveriesOverTime = [];

    /** @var list<array<string, mixed>> */
    public array $usersPerDay = [];

    /** @var list<array<string, mixed>> */
    public array $activeUsersPerDay = [];

    public function mount(): void
    {
        $this->loadReports();
    }

    public function setDays(int $days): void
    {
        if (! in_array($days, [30, 90], true)) {
            return;
        }

        $this->days = $days;
        $this->loadDiscoveriesOverTime();
    }

    public function setUsersDays(int $days): void
    {
        if (! in_array($days, [30, 90], true)) {
            return;
        }

        $this->usersDays = $days;
        $this->loadUsersPerDay();
    }

    public function setActiveUsersDays(int $days): void
    {
        if (! in_array($days, [30, 90], true)) {
            return;
        }

        $this->activeUsersDays = $days;
        $this->loadActiveUsersPerDay();
    }

    public function loadReports(): void
    {
        $this->loadMostDiscoveredPlates();
        $this->loadPostLaunchUsers();
        $this->loadUniquePlatesPerUser();
        $this->loadDiscoveriesPerUser();
        $this->loadPlatesPerSession();
        $this->loadDiscoveriesOverTime();
        $this->loadUsersPerDay();
        $this->loadActiveUsersPerDay();
    }

    protected function loadMostDiscoveredPlates(): void
    {
        $this->mostDiscoveredPlates = DB::table('user_discovered_plates as udp')
            ->join('plates as p', 'udp.plate_id', '=', 'p.id')
            ->leftJoin('series as s', 'p.series_id', '=', 's.id')
            ->leftJoin('regions as r', 's.region_id', '=', 'r.id')
            ->select(
                'p.id as plate_id',
                'p.name as plate_name',
                'r.code as region_code',
                DB::raw('COUNT(DISTINCT udp.user_id) as discovery_count')
            )
            ->groupBy('p.id', 'p.name', 'r.code')
            ->orderByDesc('discovery_count')
            ->limit(25)
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadPostLaunchUsers(): void
    {
        // A-3: Users who registered after the grand opening window (2026-08-15)
        $this->postLaunchUsers = DB::table('users as u')
            ->leftJoin(
                DB::raw('(SELECT user_id, COUNT(DISTINCT plate_id) as plate_count FROM user_discovered_plates GROUP BY user_id) as udp'),
                'u.id',
                '=',
                'udp.user_id'
            )
            ->select(
                'u.id as user_id',
                'u.email',
                'u.name',
                'u.created_at as registered_at',
                DB::raw('COALESCE(udp.plate_count, 0) as unique_plates'),
                DB::raw('CASE WHEN u.is_premium = 1 THEN \'Premium\' ELSE \'Free\' END as plan')
            )
            ->where('u.created_at', '>=', '2026-08-15 00:00:00')
            ->orderBy('u.created_at', 'desc')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadUniquePlatesPerUser(): void
    {
        $this->uniquePlatesPerUser = DB::table('user_discovered_plates as udp')
            ->join('users as u', 'udp.user_id', '=', 'u.id')
            ->select(
                'u.id as user_id',
                'u.email',
                'u.name',
                DB::raw('COUNT(DISTINCT udp.plate_id) as discovery_count')
            )
            ->groupBy('u.id', 'u.email', 'u.name')
            ->orderByDesc('discovery_count')
            ->limit(25)
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadDiscoveriesPerUser(): void
    {
        $this->discoveriesPerUser = DB::table('user_discovered_plates as udp')
            ->join('users as u', 'udp.user_id', '=', 'u.id')
            ->select(
                'u.id as user_id',
                'u.email',
                'u.name',
                DB::raw('COUNT(*) as discovery_count')
            )
            ->groupBy('u.id', 'u.email', 'u.name')
            ->orderByDesc('discovery_count')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadPlatesPerSession(): void
    {
        $this->platesPerSession = DB::table('user_discovered_plates as udp')
            ->leftJoin('discovery_sessions as ds', 'udp.session_id', '=', 'ds.id')
            ->join('users as u', 'udp.user_id', '=', 'u.id')
            ->select(
                'ds.id as session_id',
                DB::raw("COALESCE(ds.name, 'General') as session_name"),
                'u.email as user_email',
                DB::raw('COUNT(*) as discovery_count')
            )
            ->groupBy('ds.id', 'ds.name', 'u.email')
            ->orderByDesc('discovery_count')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadDiscoveriesOverTime(): void
    {
        $since = now()->subDays($this->days)->startOfDay();

        $this->discoveriesOverTime = DB::table('user_discovered_plates')
            ->select(
                DB::raw('DATE(discovered_at) as day'),
                DB::raw('COUNT(*) as discovery_count')
            )
            ->where('discovered_at', '>=', $since)
            ->groupBy('day')
            ->orderBy('day')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadUsersPerDay(): void
    {
        $since = now()->subDays($this->usersDays)->startOfDay();

        $this->usersPerDay = DB::table('users')
            ->select(
                DB::raw('DATE(created_at) as day'),
                DB::raw('COUNT(*) as user_count')
            )
            ->where('created_at', '>=', $since)
            ->groupBy('day')
            ->orderBy('day')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    protected function loadActiveUsersPerDay(): void
    {
        $since = now()->subDays($this->activeUsersDays)->startOfDay();

        $this->activeUsersPerDay = DB::table('user_discovered_plates')
            ->select(
                DB::raw('DATE(discovered_at) as day'),
                DB::raw('COUNT(DISTINCT user_id) as user_count')
            )
            ->where('discovered_at', '>=', $since)
            ->groupBy('day')
            ->orderBy('day')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }
}
