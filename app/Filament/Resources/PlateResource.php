<?php

namespace App\Filament\Resources;

use App\Filament\Resources\PlateResource\Pages;
use App\Filament\Resources\PlateResource\RelationManagers;
use App\Models\Plate;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\SoftDeletingScope;

class PlateResource extends Resource
{
    protected static ?string $model = Plate::class;

    protected static ?string $navigationIcon = 'heroicon-o-rectangle-stack';

    public static function form(Form $form): Form
    {
        return $form
            ->schema([
                Forms\Components\TextInput::make('state_code')
                    ->required()
                    ->maxLength(10),
                Forms\Components\TextInput::make('country_code')
                    ->required()
                    ->maxLength(10)
                    ->default('US'),
                Forms\Components\TextInput::make('plate_type')
                    ->required()
                    ->maxLength(100),
                Forms\Components\TextInput::make('name')
                    ->required()
                    ->maxLength(191),
                Forms\Components\TextInput::make('slug')
                    ->required()
                    ->maxLength(191),
                Forms\Components\FileUpload::make('image_filename')
                    ->image(),
                Forms\Components\TextInput::make('year_introduced'),
                Forms\Components\TextInput::make('year_discontinued'),
                Forms\Components\Toggle::make('is_active')
                    ->required(),
            ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('state_code')
                    ->searchable(),
                Tables\Columns\TextColumn::make('country_code')
                    ->searchable(),
                Tables\Columns\TextColumn::make('plate_type')
                    ->searchable(),
                Tables\Columns\TextColumn::make('name')
                    ->searchable(),
                Tables\Columns\TextColumn::make('slug')
                    ->searchable(),
                Tables\Columns\ImageColumn::make('image_filename'),
                Tables\Columns\TextColumn::make('year_introduced'),
                Tables\Columns\TextColumn::make('year_discontinued'),
                Tables\Columns\IconColumn::make('is_active')
                    ->boolean(),
                Tables\Columns\TextColumn::make('created_at')
                    ->dateTime()
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('updated_at')
                    ->dateTime()
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
            ])
            ->filters([
                //
            ])
            ->actions([
                Tables\Actions\EditAction::make(),
            ])
            ->bulkActions([
                Tables\Actions\BulkActionGroup::make([
                    Tables\Actions\DeleteBulkAction::make(),
                ]),
            ]);
    }

    public static function getRelations(): array
    {
        return [
            //
        ];
    }

    public static function getPages(): array
    {
        return [
            'index' => Pages\ListPlates::route('/'),
            'create' => Pages\CreatePlate::route('/create'),
            'edit' => Pages\EditPlate::route('/{record}/edit'),
        ];
    }
}
