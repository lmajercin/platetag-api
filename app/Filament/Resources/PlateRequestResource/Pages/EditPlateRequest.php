<?php

namespace App\Filament\Resources\PlateRequestResource\Pages;

use App\Filament\Resources\PlateRequestResource;
use Filament\Actions;
use Filament\Resources\Pages\EditRecord;

class EditPlateRequest extends EditRecord
{
    protected static string $resource = PlateRequestResource::class;

    protected function getHeaderActions(): array
    {
        return [Actions\DeleteAction::make()];
    }
}
