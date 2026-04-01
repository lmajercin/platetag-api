<?php

namespace App\Filament\Resources\PlateRequestResource\Pages;

use App\Filament\Resources\PlateRequestResource;
use Filament\Actions;
use Filament\Resources\Pages\ListRecords;

class ListPlateRequests extends ListRecords
{
    protected static string $resource = PlateRequestResource::class;

    protected function getHeaderActions(): array
    {
        return [Actions\CreateAction::make()];
    }
}
