<?php

namespace App\Filament\Pages;

use Filament\Pages\Page;
use Illuminate\Support\Facades\DB;

class PlatesWithNoImage extends Page
{
    protected static ?string $navigationIcon  = 'heroicon-o-photo';
    protected static ?string $navigationGroup = 'Administration';
    protected static ?string $navigationLabel = 'Plates Without Images';
    protected static ?int    $navigationSort  = 4;
    protected static string  $view            = 'filament.pages.plates-with-no-image';

    /** @var list<array{id: int, name: string, series_name: string|null}> */
    public array $plates = [];

    public function mount(): void
    {
        $this->load();
    }

    public function load(): void
    {
        $this->plates = DB::table('plates')
            ->leftJoin('series', 'plates.series_id', '=', 'series.id')
            ->where(function ($q) {
                $q->whereNull('plates.image_filename')
                  ->orWhere('plates.image_filename', '');
            })
            ->orderBy('plates.id')
            ->select('plates.id', 'plates.name', 'series.name as series_name')
            ->get()
            ->map(fn ($row) => (array) $row)
            ->all();
    }

    public function count(): int
    {
        return count($this->plates);
    }
}
