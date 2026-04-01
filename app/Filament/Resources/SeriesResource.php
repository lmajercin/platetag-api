<?php

namespace App\Filament\Resources;

use App\Filament\Resources\SeriesResource\Pages;
use App\Models\Region;
use App\Models\Series;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Forms\Get;
use Filament\Forms\Set;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;
use Illuminate\Support\Str;

class SeriesResource extends Resource
{
    protected static ?string $model = Series::class;
    protected static ?string $navigationIcon = 'heroicon-o-queue-list';
    protected static ?string $navigationGroup = 'Catalog';
    protected static ?int $navigationSort = 3;

    public static function form(Form $form): Form
    {
        return $form->schema([

            Forms\Components\Section::make('Identity')->schema([
                Forms\Components\TextInput::make('name')
                    ->required()->maxLength(191)
                    ->live(onBlur: true)
                    ->afterStateUpdated(fn (Set $set, ?string $state) => $set('slug', Str::slug($state ?? ''))),
                Forms\Components\TextInput::make('slug')
                    ->required()->maxLength(191),
                Forms\Components\Select::make('country_code')
                    ->label('Country')
                    ->options(['US' => 'United States', 'CA' => 'Canada', 'MX' => 'Mexico'])
                    ->required()->default('US')->live(),
                Forms\Components\Select::make('region_id')
                    ->label('Region')
                    ->options(fn (Get $get) => Region::where('country_code', $get('country_code') ?? 'US')
                        ->orderBy('name')->pluck('name', 'id'))
                    ->searchable()->required(),
            ])->columns(2),

            Forms\Components\Section::make('Design Template')->schema([
                Forms\Components\TextInput::make('background')
                    ->maxLength(255)->placeholder('e.g. Solid White'),
                Forms\Components\TextInput::make('header')
                    ->maxLength(255)->placeholder('e.g. California (script font)'),
                Forms\Components\TextInput::make('footer')
                    ->maxLength(255)->placeholder('e.g. dmv.ca.gov'),
                Forms\Components\TextInput::make('digits_style')
                    ->label('Digits Style')->maxLength(100)->placeholder('e.g. Printed, Embossed'),
            ])->columns(2),

            Forms\Components\Section::make('Active Years')->schema([
                Forms\Components\TextInput::make('year_start')
                    ->label('Year Introduced')->numeric()->minValue(1900)->maxValue(2100),
                Forms\Components\TextInput::make('year_end')
                    ->label('Year Discontinued')->numeric()->minValue(1900)->maxValue(2100)
                    ->helperText('Leave blank if still in production'),
            ])->columns(2),

            Forms\Components\Section::make('Notes & Image')->schema([
                Forms\Components\Textarea::make('notes')->columnSpanFull(),
                Forms\Components\FileUpload::make('image_filename')
                    ->label('Series Base Image')->image()->disk('public')
                    ->directory('series')->imageEditor()->maxSize(2048)->columnSpanFull(),
            ]),

            Forms\Components\Toggle::make('is_active')->default(true)->inline(false),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\ImageColumn::make('image_filename')->disk('public')->label(''),
                Tables\Columns\TextColumn::make('name')->sortable()->searchable(),
                Tables\Columns\TextColumn::make('country_code')->label('Country')->sortable(),
                Tables\Columns\TextColumn::make('region.name')->label('Region')->sortable()->toggleable(),
                Tables\Columns\TextColumn::make('year_start')->sortable()->toggleable(),
                Tables\Columns\TextColumn::make('year_end')->sortable()->toggleable(),
                Tables\Columns\IconColumn::make('is_active')->boolean()->sortable(),
            ])
            ->defaultSort('name')
            ->filters([
                Tables\Filters\TernaryFilter::make('is_active')->label('Active'),
                Tables\Filters\SelectFilter::make('country_code')
                    ->label('Country')
                    ->options(['US' => 'United States', 'CA' => 'Canada', 'MX' => 'Mexico']),
                Tables\Filters\SelectFilter::make('region_id')
                    ->label('Region')
                    ->options(Region::orderBy('name')->pluck('name', 'id'))
                    ->searchable(),
            ])
            ->actions([Tables\Actions\EditAction::make(), Tables\Actions\DeleteAction::make()])
            ->bulkActions([Tables\Actions\BulkActionGroup::make([Tables\Actions\DeleteBulkAction::make()])]);
    }

    public static function getRelations(): array { return []; }

    public static function getPages(): array
    {
        return [
            'index'  => Pages\ListSeries::route('/'),
            'create' => Pages\CreateSeries::route('/create'),
            'edit'   => Pages\EditSeries::route('/{record}/edit'),
        ];
    }
}
