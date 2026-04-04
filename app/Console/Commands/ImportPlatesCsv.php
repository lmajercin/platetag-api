<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Str;
use Illuminate\Support\Facades\DB;
use App\Models\Region;
use App\Models\Category;
use App\Models\Series;
use App\Models\Plate;

class ImportPlatesCsv extends Command
{
    protected $signature = 'plates:import-csv
                            {file : Path to the CSV file (absolute or relative to project root)}
                            {--dry-run : Preview what would be imported without writing to DB}
                            {--update : Update existing series/plates if names match (default: skip)}';

    protected $description = 'Import series and plates from a wiki_plates_scraper CSV file';

    // CSV columns we expect
    private const REQUIRED_COLS = [
        'country_code', 'region_code', 'series_name', 'plate_name',
        'plate_vehicle_class', 'plate_category',
    ];

    public function handle(): int
    {
        $path    = $this->argument('file');
        $dryRun  = $this->option('dry-run');
        $update  = $this->option('update');

        // Resolve path relative to project root if not absolute
        if (!str_starts_with($path, '/') && !preg_match('/^[A-Z]:\\\\/i', $path)) {
            $path = base_path($path);
        }

        if (!file_exists($path)) {
            $this->error("File not found: {$path}");
            return 1;
        }

        $rows = $this->readCsv($path);
        if (empty($rows)) {
            $this->error('CSV is empty or has no data rows.');
            return 1;
        }

        $this->info("Read " . count($rows) . " rows from {$path}");

        // Validate required columns
        $missing = array_diff(self::REQUIRED_COLS, array_keys($rows[0]));
        if ($missing) {
            $this->error('CSV is missing required columns: ' . implode(', ', $missing));
            return 1;
        }

        if ($dryRun) {
            $this->warn('DRY RUN — no changes will be written.');
        }

        // Pre-load lookups
        $regions    = Region::pluck('id', 'code')->all();         // code → id
        $categories = Category::pluck('id', 'name')->all();       // name → id
        $existingSeries = Series::pluck('id', 'name')->all();     // name → id
        $existingPlates = Plate::pluck('id', 'name')->all();      // name → id

        $stats = ['series_created' => 0, 'series_skipped' => 0, 'series_updated' => 0,
                  'plates_created' => 0, 'plates_skipped' => 0, 'plates_updated' => 0,
                  'errors' => []];

        $bar = $this->output->createProgressBar(count($rows));
        $bar->start();

        // Group rows by series_name to avoid redundant series upserts
        $bySeriesName = [];
        foreach ($rows as $row) {
            $bySeriesName[$row['series_name']][] = $row;
        }

        foreach ($bySeriesName as $seriesName => $seriesRows) {
            $firstRow = $seriesRows[0];

            // ── Resolve region ────────────────────────────────────────────────
            $regionCode = strtoupper(trim($firstRow['region_code']));
            $regionId   = $regions[$regionCode] ?? null;

            if (!$regionId) {
                $stats['errors'][] = "Unknown region code '{$regionCode}' in series '{$seriesName}' — skipped.";
                $bar->advance(count($seriesRows));
                continue;
            }

            // ── Upsert series ─────────────────────────────────────────────────
            $seriesId = $existingSeries[$seriesName] ?? null;

            $seriesData = [
                'name'           => substr($seriesName, 0, 191),
                'slug'           => Str::slug(substr($seriesName, 0, 191)),
                'region_id'      => $regionId,
                'country_code'   => strtoupper(trim($firstRow['country_code'])),
                'background'     => substr(trim($firstRow['series_background'] ?? ''), 0, 255),
                'header'         => substr(trim($firstRow['series_header'] ?? ''), 0, 100),
                'footer'         => substr(trim($firstRow['series_footer'] ?? ''), 0, 100),
                'notes'          => substr(trim($firstRow['series_notes'] ?? ''), 0, 1000),
                'year_start'     => $this->parseYear($firstRow['series_year_start'] ?? ''),
                'year_end'       => $this->parseYear($firstRow['series_year_end'] ?? ''),
                'image_filename' => trim($firstRow['series_image_filename'] ?? ''),
                'is_active'      => true,
            ];

            if (!$seriesId) {
                if (!$dryRun) {
                    $series   = Series::create($seriesData);
                    $seriesId = $series->id;
                    $existingSeries[$seriesName] = $seriesId;
                }
                $stats['series_created']++;
            } elseif ($update) {
                if (!$dryRun) {
                    Series::where('id', $seriesId)->update($seriesData);
                }
                $stats['series_updated']++;
            } else {
                $stats['series_skipped']++;
            }

            // ── Upsert each plate in this series ──────────────────────────────
            foreach ($seriesRows as $row) {
                $bar->advance();
                $plateName = trim($row['plate_name']);
                if (!$plateName) {
                    continue;
                }

                // Resolve category
                $categoryName = trim($row['plate_category'] ?? 'Standard Issue');
                $categoryId   = $categories[$categoryName]
                              ?? $categories['Other / Specialty']
                              ?? null;

                $plateData = [
                    'name'            => substr($plateName, 0, 191),
                    'slug'            => Str::slug(substr($plateName, 0, 191)),
                    'series_id'       => $seriesId,
                    'category_id'     => $categoryId,
                    'vehicle_class'   => trim($row['plate_vehicle_class'] ?? 'Passenger'),
                    'serial_format'   => substr(trim($row['plate_serial_format'] ?? ''), 0, 50),
                    'detail'          => substr(trim($row['plate_detail'] ?? ''), 0, 1000),
                    'image_filename'  => trim($row['plate_image_filename'] ?? ''),
                    'updates_complete'=> false,
                    'is_active'       => true,
                ];

                $plateId = $existingPlates[$plateName] ?? null;

                if (!$plateId) {
                    if (!$dryRun) {
                        $plate   = Plate::create($plateData);
                        $existingPlates[$plateName] = $plate->id;
                    }
                    $stats['plates_created']++;
                } elseif ($update) {
                    if (!$dryRun) {
                        Plate::where('id', $plateId)->update($plateData);
                    }
                    $stats['plates_updated']++;
                } else {
                    $stats['plates_skipped']++;
                }
            }
        }

        $bar->finish();
        $this->newLine(2);

        // ── Summary ───────────────────────────────────────────────────────────
        $this->table(
            ['Metric', 'Count'],
            [
                ['Series created',  $stats['series_created']],
                ['Series updated',  $stats['series_updated']],
                ['Series skipped',  $stats['series_skipped']],
                ['Plates created',  $stats['plates_created']],
                ['Plates updated',  $stats['plates_updated']],
                ['Plates skipped',  $stats['plates_skipped']],
                ['Errors',          count($stats['errors'])],
            ]
        );

        foreach ($stats['errors'] as $err) {
            $this->warn("  ! {$err}");
        }

        if ($dryRun) {
            $this->warn('DRY RUN complete — nothing was written.');
        } else {
            $this->info('Import complete.');
        }

        return 0;
    }

    private function readCsv(string $path): array
    {
        $rows    = [];
        $headers = null;
        $handle  = fopen($path, 'r');

        while (($line = fgetcsv($handle)) !== false) {
            if ($headers === null) {
                $headers = array_map('trim', $line);
                continue;
            }
            if (count($line) !== count($headers)) {
                continue; // malformed row
            }
            $rows[] = array_combine($headers, array_map('trim', $line));
        }

        fclose($handle);
        return $rows;
    }

    private function parseYear(string $val): ?int
    {
        $val = trim($val);
        if ($val === '' || $val === '0') {
            return null;
        }
        $int = (int) $val;
        return ($int >= 1900 && $int <= 2100) ? $int : null;
    }
}
