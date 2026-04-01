<?php

namespace App\Filament\Resources\PlateResource\Pages;

use App\Filament\Resources\PlateResource;
use Filament\Actions;
use Filament\Resources\Pages\ListRecords;

class ListPlates extends ListRecords
{
    protected static string $resource = PlateResource::class;

    protected function getHeaderActions(): array
    {
        return [
            Actions\CreateAction::make(),
        ];
    }
}
