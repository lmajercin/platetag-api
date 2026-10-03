<?php

namespace App\Filament\Pages;

use Filament\Pages\Page;
use Illuminate\Support\Facades\DB;

class DiscoveryMap extends Page
{
    protected static ?string $navigationIcon = 'heroicon-o-map';

    protected static ?string $navigationGroup = 'Analytics';

    protected static ?string $navigationLabel = 'Discovery Map';

    protected static ?int $navigationSort = 2;

    protected static string $view = 'filament.pages.discovery-map';

    /** @var list<array{0: float, 1: float, 2: float}> lat, lng, intensity */
    public array $heatPoints = [];

    public int $pointCount = 0;

    public function mount(): void
    {
        $this->loadHeatPoints();
    }

    protected function loadHeatPoints(): void
    {
        // Cap at 8k points for browser performance; intensity = 1 per discovery.
        $rows = DB::table('user_discovered_plates')
            ->select('latitude', 'longitude')
            ->whereNotNull('latitude')
            ->whereNotNull('longitude')
            ->orderByDesc('discovered_at')
            ->limit(8000)
            ->get();

        $this->pointCount = $rows->count();
        $this->heatPoints = $rows
            ->map(fn ($r) => [(float) $r->latitude, (float) $r->longitude, 1.0])
            ->values()
            ->all();
    }
}
