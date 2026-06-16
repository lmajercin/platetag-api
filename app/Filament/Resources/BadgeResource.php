<?php

namespace App\Filament\Resources;

use App\Filament\Resources\BadgeResource\Pages;
use App\Models\Badge;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;

class BadgeResource extends Resource
{
    protected static ?string $model = Badge::class;

    protected static ?string $navigationIcon = 'heroicon-o-trophy';

    protected static ?string $navigationGroup = 'Gamification';

    protected static ?int $navigationSort = 1;

    public static function form(Form $form): Form
    {
        return $form
            ->schema([
                Forms\Components\Section::make()->schema([
                    Forms\Components\TextInput::make('slug')
                        ->required()->maxLength(50)->unique(ignoreRecord: true)
                        ->helperText('Machine-readable ID — do not change after creation.'),
                    Forms\Components\TextInput::make('name')
                        ->required()->maxLength(100),
                    Forms\Components\Textarea::make('description')
                        ->maxLength(500)->columnSpanFull(),
                    Forms\Components\Select::make('type')
                        ->options(['geographic' => 'Geographic', 'milestone' => 'Milestone'])
                        ->required()
                        ->live(),
                    Forms\Components\TextInput::make('threshold')
                        ->numeric()->minValue(1)
                        ->visible(fn (Forms\Get $get) => $get('type') === 'milestone')
                        ->helperText('Milestone only — total plates required.'),
                    Forms\Components\TextInput::make('icon')
                        ->maxLength(100)
                        ->helperText('Phosphor icon name (e.g. Trophy, Star, Car).'),
                    Forms\Components\TextInput::make('sort_order')
                        ->numeric()->default(0),
                    Forms\Components\Toggle::make('is_active')
                        ->default(true)->inline(false)
                        ->helperText('Inactive badges are hidden from new users. Earned badges remain in user history.'),
                ])->columns(2),
            ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('sort_order')->label('Order')->sortable(),
                Tables\Columns\TextColumn::make('name')->sortable()->searchable(),
                Tables\Columns\BadgeColumn::make('type')
                    ->colors(['primary' => 'geographic', 'success' => 'milestone']),
                Tables\Columns\TextColumn::make('threshold')->label('Threshold')->sortable()
                    ->placeholder('—'),
                Tables\Columns\TextColumn::make('badge_regions_count')
                    ->counts('regions')->label('States')->placeholder('—'),
                Tables\Columns\TextColumn::make('userBadges_count')
                    ->counts('userBadges')->label('Earned by'),
                Tables\Columns\IconColumn::make('is_active')->boolean()->sortable(),
            ])
            ->defaultSort('sort_order')
            ->filters([
                Tables\Filters\SelectFilter::make('type')
                    ->options(['geographic' => 'Geographic', 'milestone' => 'Milestone']),
                Tables\Filters\TernaryFilter::make('is_active')->label('Active'),
            ])
            ->actions([
                Tables\Actions\EditAction::make(),
                // No DeleteAction here — user_badges FK is RESTRICT.
                // To delete a badge, first remove all user_badges rows for it.
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
            'index'  => Pages\ListBadges::route('/'),
            'create' => Pages\CreateBadge::route('/create'),
            'edit'   => Pages\EditBadge::route('/{record}/edit'),
        ];
    }
}
