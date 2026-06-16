<?php

namespace App\Filament\Resources;

use App\Filament\Resources\PromoCodeResource\Pages;
use App\Models\PromoCode;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;

class PromoCodeResource extends Resource
{
    protected static ?string $model = PromoCode::class;
    protected static ?string $navigationIcon = 'heroicon-o-ticket';
    protected static ?string $navigationLabel = 'Promo Codes';
    protected static ?string $navigationGroup = 'Administration';
    protected static ?int $navigationSort = 5;

    public static function form(Form $form): Form
    {
        return $form->schema([

            Forms\Components\Section::make('Code')->schema([
                Forms\Components\TextInput::make('code')
                    ->required()
                    ->maxLength(32)
                    ->minLength(8)
                    ->helperText('Minimum 8 characters. Uppercase letters, numbers, and hyphens only. Example: LAUNCH-2026')
                    ->placeholder('e.g. BETA-FREE-2026')
                    ->regex('/^[A-Z0-9\-]{8,32}$/i')
                    ->validationMessages([
                        'regex' => 'Code may only contain uppercase letters, numbers, and hyphens.',
                    ])
                    ->dehydrateStateUsing(fn (string $state) => strtoupper(trim($state)))
                    ->unique(PromoCode::class, 'code', ignoreRecord: true),

                // Only 'free' is available. 'founding_member' is intentionally excluded:
                // founding member status is set exclusively at registration within the
                // FOUNDING_MEMBER_CUTOFF window. An admin-issued code must never confer it.
                Forms\Components\Select::make('discount_type')
                    ->required()
                    ->options([
                        'free' => 'Free Access',
                    ])
                    ->default('free')
                    ->disabled()
                    ->helperText('Only "Free Access" codes are available. Founding member status is set automatically at registration.'),
            ])->columns(2),

            Forms\Components\Section::make('Validity Window')->schema([
                Forms\Components\DateTimePicker::make('starts_at')
                    ->required()
                    ->default(now())
                    ->label('Active From'),

                Forms\Components\DateTimePicker::make('expires_at')
                    ->nullable()
                    ->label('Expires At')
                    ->helperText('Leave blank for a permanent (non-expiring) code. Set a date for a windowed trial (e.g. 14-day blogger code).'),
            ])->columns(2),

            Forms\Components\Section::make('Usage Limits')->schema([
                Forms\Components\TextInput::make('max_uses')
                    ->numeric()
                    ->nullable()
                    ->minValue(1)
                    ->label('Max Uses')
                    ->helperText('Leave blank for unlimited redemptions.'),

                Forms\Components\TextInput::make('uses_count')
                    ->numeric()
                    ->disabled()
                    ->default(0)
                    ->label('Uses Count')
                    ->helperText('Read-only. Incremented on every successful redemption.'),
            ])->columns(2),

            Forms\Components\Section::make('Status')->schema([
                Forms\Components\Toggle::make('is_active')
                    ->label('Active')
                    ->default(true)
                    ->helperText('Deactivate a code without deleting it to prevent further redemptions.')
                    ->inline(false),

                Forms\Components\Textarea::make('notes')
                    ->nullable()
                    ->maxLength(1000)
                    ->rows(3)
                    ->label('Internal Notes')
                    ->helperText('Who this code was issued to, or why it was created. Not shown to users.'),
            ]),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('code')
                    ->sortable()
                    ->searchable()
                    ->copyable()
                    ->copyMessage('Code copied'),

                Tables\Columns\BadgeColumn::make('discount_type')
                    ->label('Type')
                    ->colors(['success' => 'free']),

                Tables\Columns\TextColumn::make('starts_at')
                    ->label('Active From')
                    ->dateTime('M j, Y')
                    ->sortable(),

                Tables\Columns\TextColumn::make('expires_at')
                    ->label('Expires')
                    ->dateTime('M j, Y')
                    ->placeholder('Never')
                    ->sortable(),

                Tables\Columns\TextColumn::make('uses_count')
                    ->label('Uses')
                    ->sortable(),

                Tables\Columns\TextColumn::make('max_uses')
                    ->label('Max')
                    ->placeholder('∞'),

                Tables\Columns\IconColumn::make('is_active')
                    ->boolean()
                    ->label('Active')
                    ->sortable(),

                Tables\Columns\TextColumn::make('created_at')
                    ->dateTime('M j, Y')
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
            ])
            ->filters([
                Tables\Filters\TernaryFilter::make('is_active')->label('Active'),
            ])
            ->defaultSort('created_at', 'desc')
            ->actions([
                Tables\Actions\EditAction::make(),
                Tables\Actions\DeleteAction::make(),
            ])
            ->bulkActions([
                Tables\Actions\BulkActionGroup::make([
                    Tables\Actions\DeleteBulkAction::make(),
                ]),
            ]);
    }

    public static function getRelations(): array
    {
        return [];
    }

    public static function getPages(): array
    {
        return [
            'index'  => Pages\ListPromoCodes::route('/'),
            'create' => Pages\CreatePromoCode::route('/create'),
            'edit'   => Pages\EditPromoCode::route('/{record}/edit'),
        ];
    }
}
