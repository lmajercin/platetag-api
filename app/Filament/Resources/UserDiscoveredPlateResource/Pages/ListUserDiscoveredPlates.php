<?php

namespace App\Filament\Resources\UserDiscoveredPlateResource\Pages;

use App\Filament\Resources\UserDiscoveredPlateResource;
use Filament\Resources\Pages\ListRecords;

class ListUserDiscoveredPlates extends ListRecords
{
    protected static string $resource = UserDiscoveredPlateResource::class;

    protected function getHeaderActions(): array
    {
        return [];
    }
}
