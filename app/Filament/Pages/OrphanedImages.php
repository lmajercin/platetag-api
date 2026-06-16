<?php

namespace App\Filament\Pages;

use Filament\Actions\Action;
use Filament\Notifications\Notification;
use Filament\Pages\Page;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;

class OrphanedImages extends Page
{
    protected static ?string $navigationIcon  = 'heroicon-o-photo';
    protected static ?string $navigationGroup = 'Administration';
    protected static ?string $navigationLabel = 'Orphaned Images';
    protected static ?int    $navigationSort  = 3;
    protected static string  $view            = 'filament.pages.orphaned-images';

    /** @var list<string> */
    public array $plateOrphans = [];

    /** @var list<string> */
    public array $seriesOrphans = [];

    public bool $scanned = false;

    // ─── Lifecycle ────────────────────────────────────────────────────────────

    public function mount(): void
    {
        $this->scan();
    }

    // ─── Header actions ───────────────────────────────────────────────────────

    protected function getHeaderActions(): array
    {
        return [
            Action::make('scan')
                ->label('Scan Now')
                ->icon('heroicon-o-magnifying-glass')
                ->color('gray')
                ->action('scan'),

            Action::make('deleteAll')
                ->label('Delete All Orphaned')
                ->icon('heroicon-o-trash')
                ->color('danger')
                ->requiresConfirmation()
                ->modalHeading('Delete All Orphaned Images')
                ->modalDescription(
                    fn () => 'This will permanently delete '
                        . (count($this->plateOrphans) + count($this->seriesOrphans))
                        . ' orphaned image file(s). This cannot be undone. Continue?'
                )
                ->action('deleteAllOrphans'),
        ];
    }

    // ─── Scan ─────────────────────────────────────────────────────────────────

    public function scan(): void
    {
        // Build a lookup of every filename the DB references for plates.
        // image_filename may be stored as "plates/foo.jpg" or just "foo.jpg".
        $knownPlates = DB::table('plates')
            ->whereNotNull('image_filename')
            ->pluck('image_filename')
            ->map(fn (string $f): string => ltrim(preg_replace('#^plates/#', '', $f), '/'))
            ->filter()
            ->flip() // filename => index, for O(1) isset() lookups
            ->toArray();

        $plateOrphans = [];
        foreach (Storage::disk('public')->files('plates') as $path) {
            $basename = basename($path);
            if (! isset($knownPlates[$basename])) {
                $plateOrphans[] = $basename;
            }
        }
        sort($plateOrphans);

        // Series stores 'series/filename.jpg' (Filament saves the full relative path).
        // Strip the leading 'series/' prefix so we can compare against disk basenames.
        $knownSeries = DB::table('series')
            ->whereNotNull('image_filename')
            ->pluck('image_filename')
            ->map(fn (string $f): string => ltrim(preg_replace('#^series/#', '', $f), '/'))
            ->filter()
            ->flip()
            ->toArray();

        $seriesOrphans = [];
        foreach (Storage::disk('public')->files('series') as $path) {
            $basename = basename($path);
            if (! isset($knownSeries[$basename])) {
                $seriesOrphans[] = $basename;
            }
        }
        sort($seriesOrphans);

        $this->plateOrphans  = $plateOrphans;
        $this->seriesOrphans = $seriesOrphans;
        $this->scanned       = true;
    }

    // ─── Delete one ───────────────────────────────────────────────────────────

    public function deleteOrphan(string $type, string $filename): void
    {
        // Reject anything that looks like a path traversal attempt.
        if ($filename !== basename($filename) || str_contains($filename, '..')) {
            Notification::make()->title('Invalid filename')->danger()->send();
            return;
        }

        $allowedTypes = ['plates', 'series'];
        if (! in_array($type, $allowedTypes, true)) {
            Notification::make()->title('Invalid type')->danger()->send();
            return;
        }

        $path = $type . '/' . $filename;
        if (Storage::disk('public')->exists($path)) {
            Storage::disk('public')->delete($path);
        }

        $this->scan();

        Notification::make()
            ->title('Deleted: ' . $filename)
            ->success()
            ->send();
    }

    // ─── Delete all ───────────────────────────────────────────────────────────

    public function deleteAllOrphans(): void
    {
        $count = 0;

        foreach ($this->plateOrphans as $filename) {
            if ($filename === basename($filename) && ! str_contains($filename, '..')) {
                Storage::disk('public')->delete('plates/' . $filename);
                $count++;
            }
        }

        foreach ($this->seriesOrphans as $filename) {
            if ($filename === basename($filename) && ! str_contains($filename, '..')) {
                Storage::disk('public')->delete('series/' . $filename);
                $count++;
            }
        }

        $this->scan();

        Notification::make()
            ->title("Deleted {$count} orphaned image(s)")
            ->success()
            ->send();
    }

    // ─── Summary helpers ──────────────────────────────────────────────────────

    public function totalOrphans(): int
    {
        return count($this->plateOrphans) + count($this->seriesOrphans);
    }

    public function orphanDiskSize(): string
    {
        $bytes = 0;

        foreach ($this->plateOrphans as $filename) {
            $size = Storage::disk('public')->size('plates/' . $filename);
            $bytes += $size ?: 0;
        }
        foreach ($this->seriesOrphans as $filename) {
            $size = Storage::disk('public')->size('series/' . $filename);
            $bytes += $size ?: 0;
        }

        if ($bytes >= 1048576) {
            return round($bytes / 1048576, 2) . ' MB';
        }
        return round($bytes / 1024, 1) . ' KB';
    }
}
