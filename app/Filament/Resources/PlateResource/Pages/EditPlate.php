<?php

namespace App\Filament\Resources\PlateResource\Pages;

use App\Filament\Resources\PlateResource;
use Filament\Actions;
use Filament\Resources\Pages\EditRecord;

class EditPlate extends EditRecord
{
    protected static string $resource = PlateResource::class;

    protected function getHeaderActions(): array
    {
        return [
            Actions\DeleteAction::make(),
        ];
    }
}
