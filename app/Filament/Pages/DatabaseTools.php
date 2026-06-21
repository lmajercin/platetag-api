<?php

namespace App\Filament\Pages;

use Filament\Actions\Action;
use Filament\Notifications\Notification;
use Filament\Pages\Page;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Str;

class DatabaseTools extends Page
{
    protected static ?string $navigationIcon   = 'heroicon-o-cog-8-tooth';
    protected static ?string $navigationGroup  = 'Administration';
    protected static ?string $navigationLabel  = 'DB Tools';
    protected static ?int    $navigationSort   = 2;
    protected static string  $view             = 'filament.pages.database-tools';

    public string $logOutput   = '';
    public string $lastBackup  = '';

    public function mount(): void
    {
        $this->loadLogs();
        $this->refreshLastBackup();
    }

    // ─── Header actions ───────────────────────────────────────────────────────

    protected function getHeaderActions(): array
    {
        return [
            Action::make('backup')
                ->label('Backup Database')
                ->icon('heroicon-o-arrow-down-tray')
                ->color('success')
                ->requiresConfirmation()
                ->modalHeading('Create Database Backup')
                ->modalDescription('mysqldump will write a .sql file to storage/app/backups. Continue?')
                ->action('backupDatabase'),

            Action::make('optimize')
                ->label('Optimize Tables')
                ->icon('heroicon-o-bolt')
                ->color('warning')
                ->requiresConfirmation()
                ->modalDescription('Runs OPTIMIZE TABLE on all tables in the database. Continue?')
                ->action('optimizeDatabase'),

            Action::make('clearCaches')
                ->label('Clear All Caches')
                ->icon('heroicon-o-trash')
                ->color('danger')
                ->requiresConfirmation()
                ->modalDescription('Runs artisan optimize:clear. Continue?')
                ->action('clearCaches'),

            Action::make('refreshLogs')
                ->label('Refresh Logs')
                ->icon('heroicon-o-arrow-path')
                ->color('gray')
                ->action('loadLogs'),
        ];
    }

    // ─── Actions ──────────────────────────────────────────────────────────────

    public function backupDatabase(): void
    {
        $db  = config('database.connections.mysql.database');
        $dir = storage_path('app/backups');
        if (! is_dir($dir)) { mkdir($dir, 0755, true); }

        $filename = $dir . DIRECTORY_SEPARATOR . $db . '_' . date('Ymd_His') . '.sql';

        try {
            $pdo    = \DB::connection()->getPdo();
            $tables = \DB::select('SHOW TABLES');
            $names  = array_map(fn ($r) => array_values((array) $r)[0], $tables);

            $out  = "-- PlateTag backup\n-- " . date('Y-m-d H:i:s') . "\n-- Database: {$db}\n\n";
            $out .= "SET FOREIGN_KEY_CHECKS=0;\n\n";

            foreach ($names as $table) {
                $create    = \DB::select("SHOW CREATE TABLE `{$table}`");
                $createSql = $create[0]->{'Create Table'};
                $out .= "DROP TABLE IF EXISTS `{$table}`;\n{$createSql};\n\n";

                $rows = \DB::table($table)->get();
                if ($rows->isNotEmpty()) {
                    $cols    = array_keys((array) $rows->first());
                    $colList = implode(', ', array_map(fn ($c) => "`{$c}`", $cols));
                    foreach ($rows as $row) {
                        $vals = implode(', ', array_map(
                            fn ($v) => $v === null ? 'NULL' : $pdo->quote((string) $v),
                            (array) $row
                        ));
                        $out .= "INSERT INTO `{$table}` ({$colList}) VALUES ({$vals});\n";
                    }
                    $out .= "\n";
                }
            }

            $out .= "SET FOREIGN_KEY_CHECKS=1;\n";
            file_put_contents($filename, $out);

            if (file_exists($filename) && filesize($filename) > 500) {
                $this->refreshLastBackup();
                Notification::make()->title('Backup created')->body(basename($filename))->success()->send();
            } else {
                Notification::make()->title('Backup failed')->body('File was not created or is empty.')->danger()->send();
            }
        } catch (\Exception $e) {
            Notification::make()->title('Backup failed')->body($e->getMessage())->danger()->send();
        }
    }

    public function optimizeDatabase(): void
    {
        try {
            $tables = \DB::select('SHOW TABLES');
            if (empty($tables)) {
                Notification::make()->title('Optimize failed')->body('Could not retrieve table list.')->danger()->send();
                return;
            }

            $names     = array_map(fn ($r) => array_values((array) $r)[0], $tables);
            $tableList = implode(', ', array_map(fn ($t) => "`{$t}`", $names));

            \DB::statement('OPTIMIZE TABLE ' . $tableList);

            Notification::make()->title('Tables optimized')->body(count($names) . ' tables processed.')->success()->send();
        } catch (\Exception $e) {
            Notification::make()->title('Optimize failed')->body($e->getMessage())->danger()->send();
        }
    }

    public function clearCaches(): void
    {
        Artisan::call('optimize:clear');
        $output = Artisan::output();
        Notification::make()->title('Caches cleared')->body(trim($output) ?: 'Done.')->success()->send();
    }

    public function loadLogs(): void
    {
        $logPath = storage_path('logs/laravel.log');

        if (! file_exists($logPath)) {
            $this->logOutput = '(no log file found)';
            return;
        }

        $lines       = file($logPath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        $last        = array_slice($lines, -150);
        $this->logOutput = implode("\n", array_reverse($last));
    }

    public function clearLog(): void
    {
        $logPath = storage_path('logs/laravel.log');
        if (file_exists($logPath)) { file_put_contents($logPath, ''); }
        $this->logOutput = '(log cleared)';
        Notification::make()->title('Log cleared')->success()->send();
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private function refreshLastBackup(): void
    {
        $dir   = storage_path('app/backups');
        $files = is_dir($dir) ? glob($dir . DIRECTORY_SEPARATOR . '*.sql') : [];

        if (empty($files)) {
            $this->lastBackup = 'No backups found.';
            return;
        }

        usort($files, fn ($a, $b) => filemtime($b) - filemtime($a));
        $f = $files[0];
        $this->lastBackup = basename($f) . '  (' . round(filesize($f) / 1024, 1) . ' KB)  ' . date('M j Y H:i', filemtime($f));
    }

    // ─── Stats for view ───────────────────────────────────────────────────────

    public function getDbStats(): array
    {
        try {
            $rows = \DB::select("
                SELECT table_name AS name, table_rows AS rows, (data_length + index_length) AS size_bytes
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY table_name
            ");
            return $rows;
        } catch (\Throwable) {
            return [];
        }
    }
}
