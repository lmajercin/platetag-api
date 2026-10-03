<?php

/**
 * Report: plate counts per series, ranked highest to lowest.
 * Usage: php tools/report_series_plate_counts.php [output.csv]
 */

declare(strict_types=1);

require __DIR__ . '/../vendor/autoload.php';

$app = require_once __DIR__ . '/../bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use Illuminate\Support\Facades\DB;

$outPath = $argv[1] ?? __DIR__ . '/reports/series_plate_counts_' . date('Y-m-d_His') . '.csv';

$rows = DB::select(
    'SELECT p.series_id, s.name AS series_name, COUNT(*) AS plate_count
     FROM plates p
     INNER JOIN series s ON s.id = p.series_id
     GROUP BY p.series_id, s.name
     ORDER BY plate_count DESC, p.series_id ASC'
);

$dir = dirname($outPath);
if (! is_dir($dir)) {
    mkdir($dir, 0755, true);
}

$fp = fopen($outPath, 'w');
if ($fp === false) {
    fwrite(STDERR, "Cannot write: {$outPath}\n");
    exit(1);
}

fputcsv($fp, ['series_id', 'series_name', 'plate_count']);

$totalPlates = 0;
foreach ($rows as $row) {
    fputcsv($fp, [(int) $row->series_id, $row->series_name, (int) $row->plate_count]);
    $totalPlates += (int) $row->plate_count;
}

fclose($fp);

echo "Series rows: " . count($rows) . PHP_EOL;
echo "Plates counted: {$totalPlates}" . PHP_EOL;
echo "CSV: {$outPath}" . PHP_EOL;
