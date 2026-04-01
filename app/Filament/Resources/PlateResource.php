<?php

namespace App\Filament\Resources;

use App\Filament\Resources\PlateResource\Pages;
use App\Models\Category;
use App\Models\Plate;
use App\Models\Series;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Forms\Set;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;
use Illuminate\Support\Str;

class PlateResource extends Resource
{
    protected static ?string $model = Plate::class;
    protected static ?string $navigationIcon = 'heroicon-o-identification';
    protected static ?string $navigationGroup = 'Catalog';
    protected static ?int $navigationSort = 4;

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
                Forms\Components\Select::make('series_id')
                    ->label('Series')
                    ->options(Series::orderBy('name')->pluck('name', 'id'))
                    ->searchable()->required()->columnSpan(2),
            ])->columns(2),

            Forms\Components\Section::make('Classification')->schema([
                Forms\Components\Select::make('category_id')
                    ->label('Category')
                    ->options(Category::orderBy('name')->pluck('name', 'id'))
                    ->searchable()->nullable(),
                Forms\Components\Select::make('vehicle_class')
                    ->options([
                        'Passenger'           => 'Passenger',
                        'Motorcycle'          => 'Motorcycle',
                        'Commercial / Truck'  => 'Commercial / Truck',
                        'Trailer'             => 'Trailer',
                        'Apportioned (IRP)'   => 'Apportioned (IRP)',
                        'Specialty Equipment' => 'Specialty Equipment',
                        'Other'               => 'Other',
                    ])
                    ->default('Passenger')->required(),
            ])->columns(2),

            Forms\Components\Section::make('Plate Overrides')
                ->description('Leave blank to inherit from Series')
                ->schema([
                    Forms\Components\TextInput::make('header_override')
                        ->label('Header Override')->maxLength(255)
                        ->placeholder('Overrides series header'),
                    Forms\Components\TextInput::make('footer_override')
                        ->label('Footer Override')->maxLength(255)
                        ->placeholder('Overrides series footer'),
                    Forms\Components\Textarea::make('detail')
                        ->label('Detail')->columnSpanFull()
                        ->placeholder("Unique visual elements, e.g. Vertical 'DLR' left, '24A' right"),
                    Forms\Components\TextInput::make('serial_format')
                        ->label('Serial Format')->maxLength(255)
                        ->placeholder('e.g. GS123, ABC-1234'),
                ])->columns(2),

            Forms\Components\Section::make('Image')->schema([
                Forms\Components\FileUpload::make('image_filename')
                    ->label('Plate Image')->image()->disk('public')
                    ->directory('plates')->imageEditor()->maxSize(2048)->columnSpanFull(),
            ]),

            Forms\Components\Section::make('Status')->schema([
                Forms\Components\Toggle::make('is_active')->default(true)->inline(false),
                Forms\Components\Toggle::make('updates_complete')->default(false)->inline(false),
            ])->columns(2),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\ImageColumn::make('image_filename')->disk('public')->label(''),
                Tables\Columns\TextColumn::make('name')->sortable()->searchable(),
                Tables\Columns\TextColumn::make('series.name')->label('Series')->sortable()->searchable(),
                Tables\Columns\TextColumn::make('category.name')->label('Category')->sortable()->toggleable(),
                Tables\Columns\TextColumn::make('vehicle_class')->label('Class')->sortable()->toggleable(),
                Tables\Columns\IconColumn::make('updates_complete')->boolean()->label('Done')->sortable(),
                Tables\Columns\IconColumn::make('is_active')->boolean()->sortable(),
            ])
            ->defaultSort('name')
            ->filters([
                Tables\Filters\TernaryFilter::make('is_active')->label('Active'),
                Tables\Filters\TernaryFilter::make('updates_complete')->label('Updates Complete'),
                Tables\Filters\SelectFilter::make('vehicle_class')
                    ->options([
                        'Passenger'           => 'Passenger',
                        'Motorcycle'          => 'Motorcycle',
                        'Commercial / Truck'  => 'Commercial / Truck',
                        'Trailer'             => 'Trailer',
                        'Apportioned (IRP)'   => 'Apportioned (IRP)',
                        'Specialty Equipment' => 'Specialty Equipment',
                    ]),
                Tables\Filters\SelectFilter::make('category_id')
                    ->label('Category')
                    ->options(Category::orderBy('name')->pluck('name', 'id')),
                Tables\Filters\SelectFilter::make('series_id')
                    ->label('Series')
                    ->options(Series::orderBy('name')->pluck('name', 'id'))
                    ->searchable(),
            ])
            ->actions([Tables\Actions\EditAction::make(), Tables\Actions\DeleteAction::make()])
            ->bulkActions([Tables\Actions\BulkActionGroup::make([Tables\Actions\DeleteBulkAction::make()])]);
    }

    public static function getRelations(): array { return []; }

    public static function getPages(): array
    {
        return [
            'index'  => Pages\ListPlates::route('/'),
            'create' => Pages\CreatePlate::route('/create'),
            'edit'   => Pages\EditPlate::route('/{record}/edit'),
        ];
    }
}
