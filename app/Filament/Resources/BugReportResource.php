<?php

namespace App\Filament\Resources;

use App\Filament\Resources\BugReportResource\Pages;
use App\Models\BugReport;
use App\Models\User;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;

class BugReportResource extends Resource
{
    protected static ?string $model = BugReport::class;
    protected static ?string $navigationIcon  = 'heroicon-o-bug-ant';
    protected static ?string $navigationGroup = 'Community';
    protected static ?int    $navigationSort  = 2;

    public static function form(Form $form): Form
    {
        return $form->schema([

            Forms\Components\Section::make('Report')->schema([
                Forms\Components\TextInput::make('title')
                    ->required()->maxLength(191)->columnSpanFull(),
                Forms\Components\Select::make('user_id')
                    ->label('Reported By')
                    ->options(User::orderBy('email')->pluck('email', 'id'))
                    ->searchable()->nullable(),
                Forms\Components\TextInput::make('app_version')
                    ->maxLength(50)->label('App Version')->nullable(),
                Forms\Components\Select::make('severity')
                    ->options([
                        'low'      => 'Low',
                        'medium'   => 'Medium',
                        'high'     => 'High',
                        'critical' => 'Critical',
                    ])
                    ->default('medium')->required(),
                Forms\Components\Select::make('category')
                    ->options([
                        'ui'          => 'UI / Display',
                        'api'         => 'API / Network',
                        'data'        => 'Data / Content',
                        'performance' => 'Performance',
                        'other'       => 'Other',
                    ])
                    ->default('other')->required(),
                Forms\Components\Textarea::make('description')
                    ->required()->columnSpanFull()->rows(4),
            ])->columns(2),

            Forms\Components\Section::make('Admin Response')->schema([
                Forms\Components\Select::make('status')
                    ->options([
                        'open'        => 'Open',
                        'in_progress' => 'In Progress',
                        'resolved'    => 'Resolved',
                        'wont_fix'    => "Won't Fix",
                    ])
                    ->default('open')->required(),
                Forms\Components\DateTimePicker::make('resolved_at')
                    ->label('Resolved At')->nullable(),
                Forms\Components\Textarea::make('admin_reply')
                    ->label('Reply to User (visible in app)')
                    ->helperText('This message is shown to the user in their My Submissions screen.')
                    ->columnSpanFull()->rows(3),
                Forms\Components\Textarea::make('admin_notes')
                    ->label('Internal Notes (admin only)')
                    ->columnSpanFull()->rows(2),
            ])->columns(2),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('title')->sortable()->searchable()->limit(50),
                Tables\Columns\TextColumn::make('user.email')->label('User')->sortable()->searchable()->toggleable(),
                Tables\Columns\BadgeColumn::make('severity')
                    ->colors([
                        'gray'    => 'low',
                        'warning' => 'medium',
                        'danger'  => 'high',
                        'primary' => 'critical',
                    ])
                    ->sortable(),
                Tables\Columns\BadgeColumn::make('status')
                    ->colors([
                        'warning' => 'open',
                        'primary' => 'in_progress',
                        'success' => 'resolved',
                        'gray'    => 'wont_fix',
                    ])
                    ->sortable(),
                Tables\Columns\TextColumn::make('category')->sortable()->toggleable(),
                Tables\Columns\TextColumn::make('created_at')->dateTime('M j, Y')->sortable()->toggleable(),
            ])
            ->defaultSort('created_at', 'desc')
            ->filters([
                Tables\Filters\SelectFilter::make('status')
                    ->options([
                        'open'        => 'Open',
                        'in_progress' => 'In Progress',
                        'resolved'    => 'Resolved',
                        'wont_fix'    => "Won't Fix",
                    ]),
                Tables\Filters\SelectFilter::make('severity')
                    ->options([
                        'low'      => 'Low',
                        'medium'   => 'Medium',
                        'high'     => 'High',
                        'critical' => 'Critical',
                    ]),
                Tables\Filters\SelectFilter::make('category')
                    ->options([
                        'ui'          => 'UI / Display',
                        'api'         => 'API / Network',
                        'data'        => 'Data / Content',
                        'performance' => 'Performance',
                        'other'       => 'Other',
                    ]),
            ])
            ->actions([Tables\Actions\EditAction::make(), Tables\Actions\DeleteAction::make()])
            ->bulkActions([Tables\Actions\BulkActionGroup::make([Tables\Actions\DeleteBulkAction::make()])]);
    }

    public static function getRelations(): array { return []; }

    public static function getPages(): array
    {
        return [
            'index'  => Pages\ListBugReports::route('/'),
            'create' => Pages\CreateBugReport::route('/create'),
            'edit'   => Pages\EditBugReport::route('/{record}/edit'),
        ];
    }
}
