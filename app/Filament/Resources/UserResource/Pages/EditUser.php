<?php

namespace App\Filament\Resources\UserResource\Pages;

use App\Filament\Resources\UserResource;
use Filament\Actions;
use Filament\Resources\Pages\EditRecord;
use Illuminate\Database\Eloquent\Model;

class EditUser extends EditRecord
{
    protected static string $resource = UserResource::class;

    protected function getHeaderActions(): array
    {
        return [Actions\DeleteAction::make()];
    }

    // is_premium and promo_expires_at are excluded from $fillable on the User model
    // as a mass-assignment guard on API endpoints. forceFill is safe here because
    // this page is admin-only and authenticated.
    protected function handleRecordUpdate(Model $record, array $data): Model
    {
        $protected = array_intersect_key($data, array_flip(['is_premium', 'promo_expires_at']));
        $safe      = array_diff_key($data, $protected);

        $record->fill($safe);

        if (! empty($protected)) {
            $record->forceFill($protected);
        }

        $record->save();

        return $record;
    }
}
