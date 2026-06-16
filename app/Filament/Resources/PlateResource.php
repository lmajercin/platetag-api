<?php

namespace App\Filament\Resources;

use App\Filament\Resources\PlateResource\Pages;
use App\Models\Category;
use App\Models\Plate;
use App\Models\Region;
use App\Models\Series;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Forms\Set;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;
use Filament\Tables\Actions\BulkAction;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Database\Eloquent\Model;

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
                    ->required()->maxLength(191)
                    ->rules(fn ($record) => [
                        Rule::unique('plates', 'slug')->ignore($record?->id),
                    ])
                    ->validationMessages(['unique' => 'This slug already exists on another plate. Edit the name to make it unique.']),
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
                    Forms\Components\TextInput::make('tags')
                        ->label('Search Tags')
                        ->maxLength(500)
                        ->columnSpanFull()
                        ->placeholder('Comma-separated visual keywords, e.g. horse, red, mountain, eagle, sunset')
                        ->helperText('Used for keyword search. Describe what a user would SEE — colors, animals, symbols, landmarks. Not the plate name.'),
                    Forms\Components\TextInput::make('serial_format')
                        ->label('Serial Format')->maxLength(255)
                        ->placeholder('e.g. GS123, ABC-1234'),
                ])->columns(2),

            Forms\Components\Section::make('Image')->schema([
                Forms\Components\FileUpload::make('image_filename')
                    ->label('Plate Image')->image()->disk('public')
                    ->directory('plates')->imageEditor()->maxSize(2048)->columnSpanFull()
                    ->afterStateHydrated(function ($component, $state) {
                        // DB stores bare filename; FileUpload needs an array with disk-relative path
                        // Empty/null state must be explicitly set to null — not left as '' or Livewire
                        // throws "No synthesizer found for key: ''" when serializing the component state
                        if ($state && is_string($state)) {
                            $fn = preg_replace('#^plates/#', '', $state);
                            $component->state(['plates/' . $fn]);
                        } else {
                            $component->state(null);
                        }
                    })
                    ->dehydrateStateUsing(function ($state) {
                        // Filament returns a keyed array ['uuid' => 'plates/filename.jpg']
                        // or a plain array ['plates/filename.jpg'] — extract the path value
                        if (!$state) return null;
                        $val = is_array($state) ? (array_values($state)[0] ?? null) : $state;
                        if (!$val) return null;
                        return preg_replace('#^plates/#', '', $val);
                    }),
            ]),

            Forms\Components\Section::make('Status')->schema([
                Forms\Components\Toggle::make('is_active')->default(true)->inline(false),
                Forms\Components\Toggle::make('updates_complete')->default(false)->inline(false),
                Forms\Components\Toggle::make('is_primary')
                    ->label('Primary (floats to top in Browse)')
                    ->helperText('Only one plate per series can be primary. Enabling this will clear the primary flag on any other plate in the same series.')
                    ->inline(false)
                    ->default(false),
                Forms\Components\Toggle::make('is_secondary')
                    ->label('Secondary (appears below primary, alphabetically)')
                    ->inline(false)
                    ->default(false),
            ])->columns(2),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\ImageColumn::make('image_filename')
                    ->disk('public')
                    ->getStateUsing(function ($record) {
                        $fn = $record->image_filename;
                        if (!$fn) return null;
                        // Strip accidental 'plates/' prefix stored by Filament uploader
                        $fn = preg_replace('#^plates/#', '', $fn);
                        return 'plates/' . $fn;
                    })
                    ->label('')
                    ->height(40)
                    ->width(80)
                    ->extraImgAttributes(['style' => 'object-fit:contain;background:#f3f4f6;border-radius:4px;']),
                Tables\Columns\TextColumn::make('name')->sortable()->searchable(),
                Tables\Columns\TextColumn::make('series.name')->label('Series')->sortable()->searchable(),
                Tables\Columns\TextColumn::make('detail')->searchable()->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('tags')->label('Tags')->searchable()->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('category.name')->label('Category')->sortable()->toggleable(),
                Tables\Columns\TextColumn::make('vehicle_class')->label('Class')->sortable()->toggleable(),
                Tables\Columns\IconColumn::make('updates_complete')->boolean()->label('Done')->sortable(),
                Tables\Columns\IconColumn::make('is_active')->boolean()->sortable(),
                Tables\Columns\IconColumn::make('is_primary')
                    ->label('Pri')
                    ->boolean()
                    ->sortable()
                    ->trueIcon('heroicon-s-star')
                    ->falseIcon('heroicon-o-star')
                    ->trueColor('warning')
                    ->falseColor('gray'),
                Tables\Columns\IconColumn::make('is_secondary')
                    ->label('Sec')
                    ->boolean()
                    ->sortable()
                    ->trueIcon('heroicon-s-bookmark')
                    ->falseIcon('heroicon-o-bookmark')
                    ->trueColor('info')
                    ->falseColor('gray'),
            ])
            ->defaultSort('name')
            ->defaultPaginationPageOption(50)
            ->paginationPageOptions([25, 50, 100])
            ->filters([
                Tables\Filters\TernaryFilter::make('is_active')->label('Active'),
                Tables\Filters\TernaryFilter::make('updates_complete')->label('Updates Complete'),
                Tables\Filters\TernaryFilter::make('is_primary')->label('Primary'),
                Tables\Filters\TernaryFilter::make('is_secondary')->label('Secondary'),
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
                Tables\Filters\SelectFilter::make('region')
                    ->label('Region')
                    ->options(Region::orderBy('name')->pluck('name', 'id'))
                    ->searchable()
                    ->query(fn ($query, $data) => $data['value']
                        ? $query->whereHas('series', fn ($q) => $q->where('region_id', $data['value']))
                        : $query),
                Tables\Filters\TernaryFilter::make('has_image')
                    ->label('Has Image')
                    ->nullable()
                    ->trueLabel('Has image')
                    ->falseLabel('No image')
                    ->queries(
                        true: fn ($query) => $query->whereNotNull('image_filename')->where('image_filename', '!=', ''),
                        false: fn ($query) => $query->where(fn ($q) => $q->whereNull('image_filename')->orWhere('image_filename', '')),
                        blank: fn ($query) => $query,
                    ),
            ])
            ->actions([Tables\Actions\EditAction::make(), Tables\Actions\DeleteAction::make()])
            ->bulkActions([
                Tables\Actions\BulkActionGroup::make([
                    BulkAction::make('assignCategory')
                        ->label('Assign Category')
                        ->icon('heroicon-o-tag')
                        ->visible(fn () => !app()->environment('production'))
                        ->authorize(fn () => !app()->environment('production'))
                        ->form([
                            Forms\Components\Select::make('category_id')
                                ->label('Category')
                                ->options(Category::orderBy('name')->pluck('name', 'id'))
                                ->searchable()
                                ->required(),
                        ])
                        ->action(function (Collection $records, array $data): void {
                            $records->each->update(['category_id' => $data['category_id']]);
                        })
                        ->deselectRecordsAfterCompletion(),
                    BulkAction::make('assignSeries')
                        ->label('Assign Series')
                        ->icon('heroicon-o-rectangle-stack')
                        ->visible(fn () => !app()->environment('production'))
                        ->authorize(fn () => !app()->environment('production'))
                        ->form([
                            Forms\Components\Select::make('series_id')
                                ->label('Series')
                                ->options(Series::orderBy('name')->pluck('name', 'id'))
                                ->searchable()
                                ->required(),
                        ])
                        ->action(function (Collection $records, array $data): void {
                            $records->each->update(['series_id' => $data['series_id']]);
                        })
                        ->deselectRecordsAfterCompletion(),
                    BulkAction::make('assignClass')
                        ->label('Assign Class')
                        ->icon('heroicon-o-truck')
                        ->visible(fn () => !app()->environment('production'))
                        ->authorize(fn () => !app()->environment('production'))
                        ->form([
                            Forms\Components\Select::make('vehicle_class')
                                ->label('Vehicle Class')
                                ->options([
                                    'Passenger'           => 'Passenger',
                                    'Motorcycle'          => 'Motorcycle',
                                    'Commercial / Truck'  => 'Commercial / Truck',
                                    'Trailer'             => 'Trailer',
                                    'Apportioned (IRP)'   => 'Apportioned (IRP)',
                                    'Specialty Equipment' => 'Specialty Equipment',
                                    'Other'               => 'Other',
                                ])
                                ->required(),
                        ])
                        ->action(function (Collection $records, array $data): void {
                            $records->each->update(['vehicle_class' => $data['vehicle_class']]);
                        })
                        ->deselectRecordsAfterCompletion(),
                    Tables\Actions\DeleteBulkAction::make(),
                ]),
            ]);
    }

    public static function canDeleteAny(): bool
    {
        return app()->environment('production') ? false : parent::canDeleteAny();
    }

    public static function getRelations(): array { return []; }

    public static function canEdit(Model $record): bool
    {
        return app()->environment('production') ? false : parent::canEdit($record);
    }

    public static function canCreate(): bool
    {
        return app()->environment('production') ? false : parent::canCreate();
    }

    public static function canDelete(Model $record): bool
    {
        return app()->environment('production') ? false : parent::canDelete($record);
    }

    public static function getPages(): array
    {
        return [
            'index'  => Pages\ListPlates::route('/'),
            'create' => Pages\CreatePlate::route('/create'),
            'edit'   => Pages\EditPlate::route('/{record}/edit'),
        ];
    }
}
