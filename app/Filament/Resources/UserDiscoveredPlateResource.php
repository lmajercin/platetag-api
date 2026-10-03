<?php

namespace App\Filament\Resources;

use App\Filament\Resources\UserDiscoveredPlateResource\Pages;
use App\Models\DiscoverySession;
use App\Models\User;
use App\Models\UserDiscoveredPlate;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Infolists;
use Filament\Infolists\Infolist;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

class UserDiscoveredPlateResource extends Resource
{
    protected static ?string $model = UserDiscoveredPlate::class;

    protected static ?string $navigationIcon = 'heroicon-o-bookmark-square';

    protected static ?string $navigationGroup = 'Analytics';

    protected static ?string $navigationLabel = 'Discoveries';

    protected static ?string $modelLabel = 'Discovery';

    protected static ?string $pluralModelLabel = 'Discoveries';

    protected static ?int $navigationSort = 4;

    public static function form(Form $form): Form
    {
        return $form->schema([]);
    }

    public static function infolist(Infolist $infolist): Infolist
    {
        return $infolist->schema([
            Infolists\Components\Section::make('Discovery')->schema([
                Infolists\Components\TextEntry::make('id'),
                Infolists\Components\TextEntry::make('user.email')
                    ->label('User'),
                Infolists\Components\TextEntry::make('plate.name')
                    ->label('Plate'),
                Infolists\Components\TextEntry::make('plate.series.region.code')
                    ->label('Region Code')
                    ->placeholder('—'),
                Infolists\Components\TextEntry::make('session.name')
                    ->label('Session')
                    ->formatStateUsing(fn ($state, UserDiscoveredPlate $record) => $state ?? 'General'),
                Infolists\Components\TextEntry::make('discovered_at')
                    ->dateTime('M j, Y g:i A'),
                Infolists\Components\IconEntry::make('is_first_discovery')
                    ->label('First Discovery')
                    ->boolean(),
                Infolists\Components\TextEntry::make('notes')
                    ->placeholder('—')
                    ->columnSpanFull(),
            ])->columns(2),

            Infolists\Components\Section::make('Location')->schema([
                Infolists\Components\TextEntry::make('latitude')
                    ->placeholder('—'),
                Infolists\Components\TextEntry::make('longitude')
                    ->placeholder('—'),
                Infolists\Components\TextEntry::make('location_label')
                    ->placeholder('—')
                    ->columnSpanFull(),
            ])->columns(2),

            Infolists\Components\Section::make('Record')->schema([
                Infolists\Components\TextEntry::make('session_id')
                    ->label('Session ID')
                    ->placeholder('—'),
                Infolists\Components\TextEntry::make('user_id')
                    ->label('User ID'),
                Infolists\Components\TextEntry::make('plate_id')
                    ->label('Plate ID'),
                Infolists\Components\TextEntry::make('created_at')
                    ->dateTime('M j, Y g:i A'),
                Infolists\Components\TextEntry::make('updated_at')
                    ->dateTime('M j, Y g:i A'),
            ])->columns(2),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('id')
                    ->sortable(),
                Tables\Columns\TextColumn::make('session.name')
                    ->label('Session')
                    ->formatStateUsing(fn ($state) => $state ?? 'General')
                    ->sortable()
                    ->searchable(),
                Tables\Columns\TextColumn::make('user.email')
                    ->label('User')
                    ->sortable()
                    ->searchable(),
                Tables\Columns\TextColumn::make('plate.name')
                    ->label('Plate')
                    ->description(fn (UserDiscoveredPlate $record) => $record->plate?->series?->region?->code)
                    ->sortable()
                    ->searchable(),
                Tables\Columns\TextColumn::make('discovered_at')
                    ->dateTime('M j, Y g:i A')
                    ->sortable(),
                Tables\Columns\TextColumn::make('notes')
                    ->limit(40)
                    ->toggleable()
                    ->placeholder('—'),
                Tables\Columns\TextColumn::make('longitude')
                    ->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('latitude')
                    ->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('location_label')
                    ->toggleable(isToggledHiddenByDefault: true)
                    ->placeholder('—'),
                Tables\Columns\IconColumn::make('is_first_discovery')
                    ->label('First')
                    ->boolean()
                    ->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('created_at')
                    ->dateTime('M j, Y g:i A')
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
            ])
            ->defaultSort('discovered_at', 'desc')
            ->filters([
                Tables\Filters\SelectFilter::make('user_id')
                    ->label('User')
                    ->options(fn () => User::orderBy('email')->pluck('email', 'id'))
                    ->searchable(),
                Tables\Filters\SelectFilter::make('session_id')
                    ->label('Session')
                    ->options(fn () => DiscoverySession::orderBy('name')->pluck('name', 'id'))
                    ->searchable(),
                Tables\Filters\Filter::make('discovered_at')
                    ->form([
                        Forms\Components\DatePicker::make('from')
                            ->label('From'),
                        Forms\Components\DatePicker::make('until')
                            ->label('Until'),
                    ])
                    ->query(function (Builder $query, array $data): Builder {
                        return $query
                            ->when(
                                $data['from'] ?? null,
                                fn (Builder $q, $date) => $q->whereDate('discovered_at', '>=', $date)
                            )
                            ->when(
                                $data['until'] ?? null,
                                fn (Builder $q, $date) => $q->whereDate('discovered_at', '<=', $date)
                            );
                    }),
            ])
            ->actions([
                Tables\Actions\ViewAction::make(),
            ])
            ->bulkActions([]);
    }

    public static function getRelations(): array
    {
        return [];
    }

    public static function getPages(): array
    {
        return [
            'index' => Pages\ListUserDiscoveredPlates::route('/'),
            'view'  => Pages\ViewUserDiscoveredPlate::route('/{record}'),
        ];
    }

    public static function canCreate(): bool
    {
        return false;
    }

    public static function canEdit(Model $record): bool
    {
        return false;
    }

    public static function canDelete(Model $record): bool
    {
        return false;
    }

    public static function canDeleteAny(): bool
    {
        return false;
    }

    public static function getEloquentQuery(): Builder
    {
        return parent::getEloquentQuery()
            ->with(['user', 'plate.series.region', 'session']);
    }
}
