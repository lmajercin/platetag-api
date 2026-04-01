<?php

namespace App\Filament\Resources;

use App\Filament\Resources\PlateRequestResource\Pages;
use App\Models\PlateRequest;
use App\Models\User;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;

class PlateRequestResource extends Resource
{
    protected static ?string $model = PlateRequest::class;
    protected static ?string $navigationIcon  = 'heroicon-o-inbox-arrow-down';
    protected static ?string $navigationGroup = 'Community';
    protected static ?int    $navigationSort  = 1;

    public static function form(Form $form): Form
    {
        return $form->schema([

            Forms\Components\Section::make('Request Details')->schema([
                Forms\Components\TextInput::make('plate_name')
                    ->required()->maxLength(191)
                    ->label('Plate Name / Identifier'),
                Forms\Components\TextInput::make('region_hint')
                    ->maxLength(191)->label('Region / State Hint'),
                Forms\Components\Select::make('user_id')
                    ->label('Submitted By')
                    ->options(User::orderBy('email')->pluck('email', 'id'))
                    ->searchable()->nullable(),
                Forms\Components\TextInput::make('app_version')
                    ->maxLength(50)->label('App Version')->disabled()->dehydrated(false)
                    ->hiddenOn('create'),
                Forms\Components\Textarea::make('description')
                    ->columnSpanFull()->rows(3),
                Forms\Components\FileUpload::make('image_filename')
                    ->label('Reference Image')->image()->disk('public')
                    ->directory('plate-requests')->nullable()->columnSpanFull(),
            ])->columns(2),

            Forms\Components\Section::make('Admin Review')->schema([
                Forms\Components\Select::make('status')
                    ->options([
                        'pending'   => 'Pending',
                        'reviewing' => 'Reviewing',
                        'approved'  => 'Approved',
                        'rejected'  => 'Rejected',
                    ])
                    ->default('pending')->required(),
                Forms\Components\DateTimePicker::make('resolved_at')
                    ->label('Resolved At')->nullable(),
                Forms\Components\Textarea::make('admin_notes')
                    ->columnSpanFull()->rows(3),
            ])->columns(2),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('plate_name')->sortable()->searchable(),
                Tables\Columns\TextColumn::make('region_hint')->label('Region')->sortable()->toggleable(),
                Tables\Columns\TextColumn::make('user.email')->label('User')->sortable()->searchable()->toggleable(),
                Tables\Columns\BadgeColumn::make('status')
                    ->colors([
                        'gray'    => 'pending',
                        'warning' => 'reviewing',
                        'success' => 'approved',
                        'danger'  => 'rejected',
                    ])
                    ->sortable(),
                Tables\Columns\TextColumn::make('created_at')->dateTime('M j, Y')->sortable()->toggleable(),
            ])
            ->defaultSort('created_at', 'desc')
            ->filters([
                Tables\Filters\SelectFilter::make('status')
                    ->options([
                        'pending'   => 'Pending',
                        'reviewing' => 'Reviewing',
                        'approved'  => 'Approved',
                        'rejected'  => 'Rejected',
                    ]),
            ])
            ->actions([Tables\Actions\EditAction::make(), Tables\Actions\DeleteAction::make()])
            ->bulkActions([Tables\Actions\BulkActionGroup::make([Tables\Actions\DeleteBulkAction::make()])]);
    }

    public static function getRelations(): array { return []; }

    public static function getPages(): array
    {
        return [
            'index'  => Pages\ListPlateRequests::route('/'),
            'create' => Pages\CreatePlateRequest::route('/create'),
            'edit'   => Pages\EditPlateRequest::route('/{record}/edit'),
        ];
    }
}
