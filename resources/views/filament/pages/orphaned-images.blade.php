<x-filament-panels::page>

    {{-- ─── Summary bar ─────────────────────────────────────────────────────── --}}
    <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-950 dark:text-white mb-3">Scan Summary</h2>

        @if ($this->scanned)
            @if ($this->totalOrphans() === 0)
                <p class="text-sm text-green-600 dark:text-green-400 font-medium">
                    ✓ No orphaned images found. Storage is clean.
                </p>
            @else
                <div class="flex flex-wrap gap-6 text-sm text-gray-700 dark:text-gray-300">
                    <div>
                        <span class="font-semibold text-red-500">{{ $this->totalOrphans() }}</span>
                        orphaned file(s) found
                    </div>
                    <div>
                        <span class="font-semibold">Plates:</span> {{ count($this->plateOrphans) }}
                    </div>
                    <div>
                        <span class="font-semibold">Series:</span> {{ count($this->seriesOrphans) }}
                    </div>
                    <div>
                        <span class="font-semibold">Wasted disk:</span> {{ $this->orphanDiskSize() }}
                    </div>
                </div>
            @endif
        @else
            <p class="text-sm text-gray-500 dark:text-gray-400">Press "Scan Now" to check for orphaned images.</p>
        @endif
    </div>

    {{-- ─── Plates orphans ──────────────────────────────────────────────────── --}}
    @if (count($this->plateOrphans) > 0)
        <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6 mb-6">
            <h2 class="text-base font-semibold text-gray-950 dark:text-white mb-4">
                Orphaned Plate Images
                <span class="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">
                    ({{ count($this->plateOrphans) }} file(s) — in storage/app/public/plates/ but not referenced by any plate record)
                </span>
            </h2>

            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Preview</th>
                            <th class="pb-2 pr-4 font-medium">Filename</th>
                            <th class="pb-2 pr-4 font-medium text-right">Size</th>
                            <th class="pb-2 font-medium text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->plateOrphans as $filename)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4">
                                    <img
                                        src="{{ \Illuminate\Support\Facades\Storage::disk('public')->url('plates/' . $filename) }}"
                                        alt="{{ $filename }}"
                                        class="h-12 w-auto rounded object-contain bg-gray-100 dark:bg-gray-800"
                                        loading="lazy"
                                    >
                                </td>
                                <td class="py-2 pr-4 font-mono text-gray-800 dark:text-gray-200 break-all">
                                    {{ $filename }}
                                </td>
                                <td class="py-2 pr-4 text-right text-gray-500 dark:text-gray-400">
                                    @php
                                        $bytes = \Illuminate\Support\Facades\Storage::disk('public')->size('plates/' . $filename) ?: 0;
                                        echo $bytes >= 1048576
                                            ? round($bytes / 1048576, 2) . ' MB'
                                            : round($bytes / 1024, 1) . ' KB';
                                    @endphp
                                </td>
                                <td class="py-2 text-right">
                                    <button
                                        wire:click="deleteOrphan('plates', '{{ $filename }}')"
                                        wire:confirm="Delete {{ $filename }}? This cannot be undone."
                                        class="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition">
                                        Delete
                                    </button>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
    @endif

    {{-- ─── Series orphans ──────────────────────────────────────────────────── --}}
    @if (count($this->seriesOrphans) > 0)
        <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6 mb-6">
            <h2 class="text-base font-semibold text-gray-950 dark:text-white mb-4">
                Orphaned Series Images
                <span class="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">
                    ({{ count($this->seriesOrphans) }} file(s) — in storage/app/public/series/ but not referenced by any series record)
                </span>
            </h2>

            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium">Preview</th>
                            <th class="pb-2 pr-4 font-medium">Filename</th>
                            <th class="pb-2 pr-4 font-medium text-right">Size</th>
                            <th class="pb-2 font-medium text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->seriesOrphans as $filename)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4">
                                    <img
                                        src="{{ \Illuminate\Support\Facades\Storage::disk('public')->url('series/' . $filename) }}"
                                        alt="{{ $filename }}"
                                        class="h-12 w-auto rounded object-contain bg-gray-100 dark:bg-gray-800"
                                        loading="lazy"
                                    >
                                </td>
                                <td class="py-2 pr-4 font-mono text-gray-800 dark:text-gray-200 break-all">
                                    {{ $filename }}
                                </td>
                                <td class="py-2 pr-4 text-right text-gray-500 dark:text-gray-400">
                                    @php
                                        $bytes = \Illuminate\Support\Facades\Storage::disk('public')->size('series/' . $filename) ?: 0;
                                        echo $bytes >= 1048576
                                            ? round($bytes / 1048576, 2) . ' MB'
                                            : round($bytes / 1024, 1) . ' KB';
                                    @endphp
                                </td>
                                <td class="py-2 text-right">
                                    <button
                                        wire:click="deleteOrphan('series', '{{ $filename }}')"
                                        wire:confirm="Delete {{ $filename }}? This cannot be undone."
                                        class="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition">
                                        Delete
                                    </button>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
    @endif

    {{-- ─── Empty state ─────────────────────────────────────────────────────── --}}
    @if ($this->scanned && $this->totalOrphans() === 0)
        <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6">
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                No orphaned images in plates or series folders.
            </p>
        </div>
    @endif

</x-filament-panels::page>
