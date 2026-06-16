<x-filament-panels::page>

    {{-- ─── Summary bar ─────────────────────────────────────────────────────── --}}
    <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6 mb-6">
        @if ($this->count() === 0)
            <p class="text-sm text-green-600 dark:text-green-400 font-medium">
                ✓ All plates have an image assigned.
            </p>
        @else
            <p class="text-sm text-amber-600 dark:text-amber-400 font-medium">
                {{ $this->count() }} plate(s) have no image assigned. Click <strong>Edit</strong> on any row to add one.
            </p>
        @endif
    </div>

    {{-- ─── Table ───────────────────────────────────────────────────────────── --}}
    @if ($this->count() > 0)
        <div class="fi-section rounded-xl bg-white shadow-sm ring-1 ring-gray-950/5 dark:bg-gray-900 dark:ring-white/10 p-6">
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-200 dark:border-white/10 text-left text-gray-500 dark:text-gray-400">
                            <th class="pb-2 pr-4 font-medium w-16">ID</th>
                            <th class="pb-2 pr-4 font-medium">Plate Name</th>
                            <th class="pb-2 pr-4 font-medium">Series</th>
                            <th class="pb-2 font-medium text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($this->plates as $plate)
                            <tr class="border-b border-gray-100 dark:border-white/5">
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $plate['id'] }}</td>
                                <td class="py-2 pr-4 text-gray-800 dark:text-gray-200">{{ $plate['name'] }}</td>
                                <td class="py-2 pr-4 text-gray-500 dark:text-gray-400">{{ $plate['series_name'] ?? '—' }}</td>
                                <td class="py-2 text-right">
                                    <a href="{{ \App\Filament\Resources\PlateResource::getUrl('edit', ['record' => $plate['id']]) }}"
                                       class="text-xs text-primary-600 hover:text-primary-800 dark:text-primary-400 dark:hover:text-primary-200 transition">
                                        Edit
                                    </a>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
    @endif

</x-filament-panels::page>
