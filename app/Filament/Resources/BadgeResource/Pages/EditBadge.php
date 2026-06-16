<?php

namespace App\Filament\Resources\BadgeResource\Pages;

use App\Filament\Resources\BadgeResource;
use Filament\Resources\Pages\EditRecord;

class EditBadge extends EditRecord
{
    protected static string $resource = BadgeResource::class;

    // No DeleteAction — user_badges FK is RESTRICT.
    // To remove a badge, first clear all user_badges rows for it.
    protected function getHeaderActions(): array
    {
        return [];
    }
}
