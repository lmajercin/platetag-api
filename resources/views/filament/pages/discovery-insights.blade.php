<x-filament-panels::page>
    <style>
        .pt-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
        .pt-kpi {
            border-radius: 1rem; padding: 1.1rem 1.25rem;
            background: linear-gradient(145deg, #fffbeb 0%, #ffffff 55%);
            border: 1px solid rgba(245, 158, 11, 0.25);
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        .dark .pt-kpi {
            background: linear-gradient(145deg, rgba(245,158,11,0.12) 0%, rgba(17,24,39,1) 60%);
            border-color: rgba(245,158,11,0.2);
        }
        .pt-kpi-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #b45309; }
        .dark .pt-kpi-label { color: #fbbf24; }
        .pt-kpi-value { font-size: 1.75rem; font-weight: 800; color: #111827; line-height: 1.2; margin-top: 0.25rem; }
        .dark .pt-kpi-value { color: #f9fafb; }
        .pt-kpi-sub { font-size: 0.75rem; color: #6b7280; margin-top: 0.2rem; }
        .dark .pt-kpi-sub { color: #9ca3af; }
        .pt-section {
            border-radius: 1rem; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;
            background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            border: 1px solid rgba(17,24,39,0.06);
        }
        .dark .pt-section { background: #111827; border-color: rgba(255,255,255,0.08); }
        .pt-section h2 { font-size: 1rem; font-weight: 700; color: #111827; margin-bottom: 0.25rem; }
        .dark .pt-section h2 { color: #f3f4f6; }
        .pt-section .pt-hint { font-size: 0.8rem; color: #6b7280; margin-bottom: 1rem; }
        .dark .pt-section .pt-hint { color: #9ca3af; }
        .pt-bars { display: flex; flex-direction: column; gap: 0.45rem; }
        .pt-bar-row { display: grid; grid-template-columns: 3.5rem 1fr 3.5rem; gap: 0.6rem; align-items: center; }
        .pt-bar-label { font-size: 0.75rem; color: #6b7280; text-align: right; }
        .dark .pt-bar-label { color: #9ca3af; }
        .pt-bar-track { height: 0.65rem; border-radius: 999px; background: #f3f4f6; overflow: hidden; }
        .dark .pt-bar-track { background: #1f2937; }
        .pt-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f59e0b, #f97316); }
        .pt-bar-count { font-size: 0.75rem; font-weight: 600; color: #374151; text-align: right; }
        .dark .pt-bar-count { color: #d1d5db; }
        .pt-hour-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 0.35rem; }
        @media (max-width: 900px) { .pt-hour-grid { grid-template-columns: repeat(6, 1fr); } }
        .pt-hour-cell { text-align: center; }
        .pt-hour-col {
            height: 90px; display: flex; align-items: flex-end; justify-content: center;
            background: #f9fafb; border-radius: 0.4rem; padding: 0.25rem;
        }
        .dark .pt-hour-col { background: #1f2937; }
        .pt-hour-col-bar {
            width: 70%; border-radius: 0.25rem 0.25rem 0 0;
            background: linear-gradient(180deg, #fbbf24, #d97706); min-height: 2px;
        }
        .pt-hour-label { font-size: 0.65rem; color: #9ca3af; margin-top: 0.2rem; }
        .pt-table { width: 100%; font-size: 0.875rem; }
        .pt-table th { text-align: left; font-weight: 600; color: #6b7280; padding-bottom: 0.5rem; border-bottom: 1px solid #e5e7eb; }
        .dark .pt-table th { color: #9ca3af; border-color: rgba(255,255,255,0.1); }
        .pt-table td { padding: 0.45rem 0; border-bottom: 1px solid #f3f4f6; color: #1f2937; }
        .dark .pt-table td { border-color: rgba(255,255,255,0.05); color: #e5e7eb; }
        .pt-table .num { text-align: right; font-variant-numeric: tabular-nums; }
        .pt-chip-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
        .pt-chip {
            padding: 0.3rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
            border: 1px solid #d1d5db; color: #4b5563; background: transparent; cursor: pointer;
        }
        .dark .pt-chip { border-color: rgba(255,255,255,0.2); color: #d1d5db; }
        .pt-chip.active { background: #d97706; border-color: #d97706; color: #fff; }
        .pt-line-chart { display: flex; align-items: flex-end; gap: 2px; height: 120px; padding-top: 0.5rem; }
        .pt-line-col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; min-width: 0; }
        .pt-line-bar { width: 100%; max-width: 10px; border-radius: 2px 2px 0 0; background: #f59e0b; min-height: 1px; }
        .pt-line-bar.alt { background: #fb923c; opacity: 0.85; }
        .pt-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
        @media (max-width: 900px) { .pt-two-col { grid-template-columns: 1fr; } }
    </style>

    {{-- KPI strip --}}
    <div class="pt-kpi-grid">
        <div class="pt-kpi">
            <div class="pt-kpi-label">Discoveries w/ location</div>
            <div class="pt-kpi-value">{{ number_format($this->pctDiscoveriesWithLocation, 1) }}%</div>
            <div class="pt-kpi-sub">{{ number_format($this->discoveriesWithLocation) }} of {{ number_format($this->totalDiscoveries) }}</div>
        </div>
        <div class="pt-kpi">
            <div class="pt-kpi-label">Without location</div>
            <div class="pt-kpi-value">{{ number_format(100 - $this->pctDiscoveriesWithLocation, 1) }}%</div>
            <div class="pt-kpi-sub">{{ number_format($this->discoveriesWithoutLocation) }} discoveries</div>
        </div>
        <div class="pt-kpi">
            <div class="pt-kpi-label">Collectors who shared geo</div>
            <div class="pt-kpi-value">{{ number_format($this->pctUsersWithLocation, 1) }}%</div>
            <div class="pt-kpi-sub">{{ $this->usersEverWithLocation }} of {{ $this->activeCollectors }} active collectors</div>
        </div>
        <div class="pt-kpi">
            <div class="pt-kpi-label">Never shared geo</div>
            <div class="pt-kpi-value">{{ $this->usersNeverWithLocation }}</div>
            <div class="pt-kpi-sub">Collectors with discoveries but no coords</div>
        </div>
    </div>

    <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
        “Shared geo” is inferred from discoveries that include latitude/longitude — the app does not yet store the OS permission flag itself.
    </p>

    {{-- Geo adoption over time --}}
    <div class="pt-section">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-1">
            <h2>Location attachment over time</h2>
            <div class="pt-chip-row" style="margin:0">
                <button type="button" wire:click="setDays(30)" class="pt-chip {{ $days === 30 ? 'active' : '' }}">30 days</button>
                <button type="button" wire:click="setDays(90)" class="pt-chip {{ $days === 90 ? 'active' : '' }}">90 days</button>
            </div>
        </div>
        <p class="pt-hint">Daily snapshots: % of that day’s discoveries that included location (amber), and % of that day’s active collectors who shared location (orange).</p>
        @if (count($this->geoSnapshots) === 0)
            <p class="text-sm text-gray-500">No snapshot data yet. Run <code>php artisan analytics:snapshot-geo --backfill</code> once.</p>
        @else
            @php
                $maxPct = max(1, collect($this->geoSnapshots)->max(fn ($r) => max($r['pct_discoveries'], $r['pct_users'])));
            @endphp
            <div class="pt-line-chart">
                @foreach ($this->geoSnapshots as $row)
                    <div class="pt-line-col" title="{{ $row['day'] }}: discoveries {{ $row['pct_discoveries'] }}%, users {{ $row['pct_users'] }}%">
                        <div class="pt-line-bar" style="height: {{ ($row['pct_discoveries'] / $maxPct) * 100 }}%"></div>
                        <div class="pt-line-bar alt" style="height: {{ ($row['pct_users'] / $maxPct) * 100 }}%; margin-top: 1px;"></div>
                    </div>
                @endforeach
            </div>
            <div class="flex justify-between text-xs text-gray-400 mt-2">
                <span>{{ $this->geoSnapshots[0]['day'] ?? '' }}</span>
                <span>{{ $this->geoSnapshots[count($this->geoSnapshots)-1]['day'] ?? '' }}</span>
            </div>
        @endif
    </div>

    {{-- Time patterns --}}
    <div class="pt-two-col">
        <div class="pt-section">
            <h2>Day of week</h2>
            <p class="pt-hint">Discoveries in the last {{ $days }} days (server timezone).</p>
            @php $maxWd = max(1, collect($this->byWeekday)->max('count')); @endphp
            <div class="pt-bars">
                @foreach ($this->byWeekday as $row)
                    <div class="pt-bar-row">
                        <div class="pt-bar-label">{{ $row['label'] }}</div>
                        <div class="pt-bar-track">
                            <div class="pt-bar-fill" style="width: {{ ($row['count'] / $maxWd) * 100 }}%"></div>
                        </div>
                        <div class="pt-bar-count">{{ $row['count'] }}</div>
                    </div>
                @endforeach
            </div>
        </div>

        <div class="pt-section">
            <h2>Hour of day (UTC)</h2>
            <p class="pt-hint">When discoveries are logged. Convert mentally for US timezones (−4 to −8).</p>
            @php $maxH = max(1, collect($this->byHour)->max('count')); @endphp
            <div class="pt-hour-grid">
                @foreach ($this->byHour as $row)
                    <div class="pt-hour-cell">
                        <div class="pt-hour-col">
                            <div class="pt-hour-col-bar" style="height: {{ ($row['count'] / $maxH) * 100 }}%"></div>
                        </div>
                        <div class="pt-hour-label">{{ $row['hour'] }}</div>
                    </div>
                @endforeach
            </div>
        </div>
    </div>

    {{-- Hotspots --}}
    <div class="pt-two-col">
        <div class="pt-section">
            <h2>Plate origin hotspots</h2>
            <p class="pt-hint">Which regions’ plates are being collected most (catalog region of the plate).</p>
            @if (count($this->regionalHotspots) === 0)
                <p class="text-sm text-gray-500">No data.</p>
            @else
                <table class="pt-table">
                    <thead>
                        <tr>
                            <th>Region</th>
                            <th>Country</th>
                            <th class="num">Discoveries</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->regionalHotspots as $row)
                            <tr>
                                <td>{{ $row['region_name'] }} <span class="text-gray-400">({{ $row['region_code'] }})</span></td>
                                <td>{{ $row['country_code'] }}</td>
                                <td class="num">{{ number_format($row['discovery_count']) }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            @endif
        </div>

        <div class="pt-section">
            <h2>Sighting location hotspots</h2>
            <p class="pt-hint">Where collectors were when they logged (device location label).</p>
            @if (count($this->locationLabelHotspots) === 0)
                <p class="text-sm text-gray-500">No location labels yet.</p>
            @else
                <table class="pt-table">
                    <thead>
                        <tr>
                            <th>Location</th>
                            <th class="num">Discoveries</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->locationLabelHotspots as $row)
                            <tr>
                                <td>{{ $row['location_label'] }}</td>
                                <td class="num">{{ number_format($row['discovery_count']) }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            @endif
        </div>
    </div>
</x-filament-panels::page>
