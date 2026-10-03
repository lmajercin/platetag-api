<x-filament-panels::page>
    <style>
        .pt-section {
            border-radius: 1rem; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;
            background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            border: 1px solid rgba(17,24,39,0.06);
        }
        .dark .pt-section { background: #111827; border-color: rgba(255,255,255,0.08); }
        .pt-section h2 { font-size: 1rem; font-weight: 700; color: #111827; margin-bottom: 0.75rem; }
        .dark .pt-section h2 { color: #f3f4f6; }
        .pt-banner {
            border-radius: 1rem; padding: 1rem 1.25rem; margin-bottom: 1.25rem;
            background: linear-gradient(90deg, #fffbeb, #fff);
            border: 1px solid rgba(245,158,11,0.3);
            font-size: 0.875rem; color: #78350f;
        }
        .dark .pt-banner {
            background: linear-gradient(90deg, rgba(245,158,11,0.15), #111827);
            color: #fde68a; border-color: rgba(245,158,11,0.25);
        }
        .pt-chip {
            padding: 0.3rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
            border: 1px solid #d1d5db; color: #4b5563; background: transparent; cursor: pointer;
        }
        .dark .pt-chip { border-color: rgba(255,255,255,0.2); color: #d1d5db; }
        .pt-chip.active { background: #d97706; border-color: #d97706; color: #fff; }
        .pt-nav {
            display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; margin-bottom: 1.25rem;
            padding: 0.85rem 1.1rem; border-radius: 0.75rem;
            background: #f9fafb; border: 1px solid rgba(17,24,39,0.08);
        }
        .dark .pt-nav { background: #1f2937; border-color: rgba(255,255,255,0.08); }
        .pt-nav a {
            font-size: 0.875rem; font-weight: 600; color: #b45309; text-decoration: none;
        }
        .dark .pt-nav a { color: #fbbf24; }
        .pt-nav a:hover { text-decoration: underline; }
        .pt-nav span { color: #9ca3af; font-size: 0.875rem; }
    </style>

    <nav class="pt-nav" aria-label="Analytics quick links">
        <span>Go to:</span>
        <a href="{{ \App\Filament\Pages\DiscoveryInsights::getUrl() }}">Discovery Insights</a>
        <a href="{{ \App\Filament\Pages\DiscoveryMap::getUrl() }}">Discovery Map</a>
        <a href="{{ \App\Filament\Resources\UserDiscoveredPlateResource::getUrl() }}">Discoveries</a>
    </nav>

    <div class="pt-banner">
        Detailed discovery tables — signups, active users, top plates, and per-user counts.
    </div>

    <div class="pt-section">
        <h2>Post-Launch Users (registered after 2026-08-15)</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">Users who joined after the grand opening premium grant window closed. Shows organic post-launch growth.</p>
        @if (count($this->postLaunchUsers) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No users registered after 2026-08-15.</p>
        @else
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">{{ count($this->postLaunchUsers) }} users total.</p>
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Email</th>
                            <th class="pb-2 pr-4 font-medium">Name</th>
                            <th class="pb-2 pr-4 font-medium">Registered</th>
                            <th class="pb-2 pr-4 font-medium text-right">Unique Plates</th>
                            <th class="pb-2 font-medium">Plan</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->postLaunchUsers as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['email'] }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $row['name'] ?? '—' }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ \Carbon\Carbon::parse($row['registered_at'])->format('Y-m-d') }}</td>
                                <td class="py-2 pr-4 text-right text-gray-800 dark:text-gray-200">{{ $row['unique_plates'] }}</td>
                                <td class="py-2">
                                    <span class="{{ $row['plan'] === 'Premium' ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-gray-500 dark:text-gray-400' }}">
                                        {{ $row['plan'] }}
                                    </span>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <h2>Most Collected Plates (Top 25)</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">Ranked by number of distinct users who have this plate in their collection. Each user counted once per plate regardless of how many times they discovered it.</p>
        @if (count($this->mostDiscoveredPlates) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No discovery data yet.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Plate</th>
                            <th class="pb-2 pr-4 font-medium">Region</th>
                            <th class="pb-2 font-medium text-right">Unique Users</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->mostDiscoveredPlates as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['plate_name'] }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $row['region_code'] ?? '—' }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['discovery_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <h2>Most Unique Plates per user (Top 25)</h2>
        @if (count($this->uniquePlatesPerUser) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No discovery data yet.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">User</th>
                            <th class="pb-2 pr-4 font-medium">Name</th>
                            <th class="pb-2 font-medium text-right">Discoveries</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->uniquePlatesPerUser as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['email'] }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $row['name'] ?? '—' }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['discovery_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <h2>Discoveries Per User</h2>
        @if (count($this->discoveriesPerUser) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No discovery data yet.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">User</th>
                            <th class="pb-2 pr-4 font-medium">Name</th>
                            <th class="pb-2 font-medium text-right">Discoveries</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->discoveriesPerUser as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['email'] }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $row['name'] ?? '—' }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['discovery_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <h2>Plates Per Session</h2>
        @if (count($this->platesPerSession) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No discovery data yet.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Session</th>
                            <th class="pb-2 pr-4 font-medium">User</th>
                            <th class="pb-2 font-medium text-right">Discoveries</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->platesPerSession as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['session_name'] }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $row['user_email'] }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['discovery_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 style="margin:0">Discoveries Over Time</h2>
            <div class="flex gap-2">
                <button type="button" wire:click="setDays(30)" class="pt-chip {{ $days === 30 ? 'active' : '' }}">Last 30 days</button>
                <button type="button" wire:click="setDays(90)" class="pt-chip {{ $days === 90 ? 'active' : '' }}">Last 90 days</button>
            </div>
        </div>
        @if (count($this->discoveriesOverTime) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No discoveries in the selected period.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Date</th>
                            <th class="pb-2 font-medium text-right">Discoveries</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->discoveriesOverTime as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['day'] }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['discovery_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 style="margin:0">Number of Users Per Day</h2>
            <div class="flex gap-2">
                <button type="button" wire:click="setUsersDays(30)" class="pt-chip {{ $usersDays === 30 ? 'active' : '' }}">Last 30 days</button>
                <button type="button" wire:click="setUsersDays(90)" class="pt-chip {{ $usersDays === 90 ? 'active' : '' }}">Last 90 days</button>
            </div>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">New user registrations per day.</p>
        @if (count($this->usersPerDay) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No new users in the selected period.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Date</th>
                            <th class="pb-2 font-medium text-right">Users</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->usersPerDay as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['day'] }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['user_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

    <div class="pt-section">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 style="margin:0">Active Users Per Day</h2>
            <div class="flex gap-2">
                <button type="button" wire:click="setActiveUsersDays(30)" class="pt-chip {{ $activeUsersDays === 30 ? 'active' : '' }}">Last 30 days</button>
                <button type="button" wire:click="setActiveUsersDays(90)" class="pt-chip {{ $activeUsersDays === 90 ? 'active' : '' }}">Last 90 days</button>
            </div>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">Unique users who logged at least one plate discovery per day.</p>
        @if (count($this->activeUsersPerDay) === 0)
            <p class="text-sm text-gray-500 dark:text-gray-400">No active users in the selected period.</p>
        @else
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Date</th>
                            <th class="pb-2 font-medium text-right">Users</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->activeUsersPerDay as $row)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $row['day'] }}</td>
                                <td class="py-2 text-right text-gray-800 dark:text-gray-200">{{ $row['user_count'] }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>
</x-filament-panels::page>
