<x-filament-panels::page>

    {{-- ─── Table stats ─────────────────────────────────────────────────────── --}}
    <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-950 dark:text-white mb-4">Table Statistics</h2>

        <div class="overflow-x-auto">
            <table class="min-w-full text-sm">
                <thead>
                    <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                        <th class="pb-2 pr-4 font-medium">Table</th>
                        <th class="pb-2 pr-4 font-medium text-right">Rows (est.)</th>
                        <th class="pb-2 font-medium text-right">Size</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($this->getDbStats() as $row)
                        <tr class="border-b border-gray-100 dark:border-white/5">
                            <td class="py-1.5 pr-4 font-mono text-gray-800 dark:text-gray-200">{{ $row->name }}</td>
                            <td class="py-1.5 pr-4 text-right text-gray-600 dark:text-gray-400">{{ number_format($row->rows ?? 0) }}</td>
                            <td class="py-1.5 text-right text-gray-600 dark:text-gray-400">
                                {{ $row->size_bytes >= 1048576
                                    ? round($row->size_bytes / 1048576, 2) . ' MB'
                                    : round($row->size_bytes / 1024, 1) . ' KB' }}
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    </div>

    {{-- ─── Last backup ─────────────────────────────────────────────────────── --}}
    <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-950 dark:text-white mb-1">Last Backup</h2>
        <p class="text-sm font-mono text-gray-600 dark:text-gray-400">{{ $this->lastBackup }}</p>
    </div>

    {{-- ─── Log viewer ──────────────────────────────────────────────────────── --}}
    <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6">
        <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold text-gray-950 dark:text-white">Laravel Log (last 150 lines, newest first)</h2>
            <button
                wire:click="clearLog"
                onclick="return confirm('Clear the entire log file?')"
                class="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition">
                Clear Log
            </button>
        </div>

        <pre class="overflow-x-auto overflow-y-auto max-h-96 rounded-lg bg-gray-950 text-green-400 text-xs p-4 leading-relaxed whitespace-pre-wrap break-words">{{ $this->logOutput ?: '(empty)' }}</pre>
    </div>

</x-filament-panels::page>
