<?php

namespace App\Console\Commands;

use App\Models\Plate;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

class TagPlatesWithVisionHeaderFooter extends Command
{
    protected $signature = 'tagger:header-footer-series
                            {series : Series ID to process (e.g. 820)}
                            {--limit=0 : Maximum plates to process (0 = all eligible in series)}
                            {--plate=0 : Process a single plate by ID (must belong to the series)}
                            {--dry-run : List eligible plates only — no OpenAI calls, no DB writes}';

    protected $description = 'GPT-4o Vision header/footer tagger by series — writes header_override, footer_override, sets updates_complete=1. Local WAMP only.';

    private const LOG_FILE = 'logs/tagger-header-footer-failures.log';

    private const MAX_FIELD_LENGTH = 255;

    public function handle(): int
    {
        ini_set('memory_limit', '512M');

        $seriesId = (int) $this->argument('series');

        if ($seriesId <= 0) {
            $this->error('Series ID must be a positive integer.');

            return self::FAILURE;
        }

        if ($this->option('dry-run')) {
            return $this->runDryRun($seriesId);
        }

        $apiKey = config('services.openai.key');

        if (empty($apiKey)) {
            $this->error('OPENAI_API_KEY is not set. Add it to .env and try again.');

            return self::FAILURE;
        }

        $plates = $this->buildQuery($seriesId)->get();

        if ($plates->isEmpty()) {
            $this->info("No eligible plates found for series {$seriesId}.");

            return self::SUCCESS;
        }

        $total = $plates->count();

        $this->info("Header/footer tagger — series {$seriesId}: processing {$total} plate(s)...");
        $this->warn('Writes header_override + footer_override from image; sets updates_complete = 1.');

        $processed = 0;
        $skipped   = 0;
        $failed    = 0;

        $bar = $this->output->createProgressBar($total);
        $bar->start();

        foreach ($plates as $plate) {
            $result = $this->processPlate($plate, $apiKey);

            match ($result) {
                'ok'    => $processed++,
                'skip'  => $skipped++,
                default => $failed++,
            };

            $bar->advance();

            unset($plate);
            gc_collect_cycles();

            if ($processed + $skipped + $failed < $total) {
                sleep(1);
            }
        }

        $bar->finish();
        $this->newLine(2);
        $this->table(
            ['Series', 'Processed', 'Skipped', 'Failed'],
            [[$seriesId, $processed, $skipped, $failed]]
        );

        $this->appendRunSummary($seriesId, $processed, $skipped, $failed);

        if ($failed > 0) {
            $this->line('  Failures logged to: storage/' . self::LOG_FILE);
        }

        return $failed > 0 ? self::FAILURE : self::SUCCESS;
    }

    private function buildQuery(int $seriesId)
    {
        $query = Plate::with('series.region')
            ->where('series_id', $seriesId)
            ->whereNotNull('image_filename')
            ->where('image_filename', '!=', '');

        if ($this->option('plate')) {
            $query->where('id', (int) $this->option('plate'));
        }

        $this->applyEligibilityScope($query);

        return $query->orderBy('id')->when(
            $this->option('limit') > 0,
            fn ($q) => $q->limit((int) $this->option('limit'))
        );
    }

    private function applyEligibilityScope($query): void
    {
        $query->where(fn ($q) => $q->whereNull('header_override')->orWhere('header_override', ''))
              ->where(fn ($q) => $q->whereNull('footer_override')->orWhere('footer_override', ''))
              ->where('updates_complete', false);
    }

    private function runDryRun(int $seriesId): int
    {
        $plates = $this->buildQuery($seriesId)->get();

        $this->info("DRY RUN — series {$seriesId}: {$plates->count()} eligible plate(s). No API calls, no DB writes.");

        if ($plates->isEmpty()) {
            return self::SUCCESS;
        }

        $rows = $plates->map(fn (Plate $plate) => [
            $plate->id,
            $plate->name,
            $plate->header_override ?: '(null)',
            $plate->footer_override ?: '(null)',
            $plate->updates_complete ? '1' : '0',
            preg_replace('#^plates/#', '', $plate->image_filename ?? ''),
        ])->all();

        $this->table(['ID', 'Name', 'header', 'footer', 'done', 'image'], $rows);

        return self::SUCCESS;
    }

    private function logFailure(Plate $plate, string $reason): void
    {
        $line = sprintf(
            "[%s] FAILED  Series #%-4d  Plate #%-6d  %-50s  %s\n",
            now()->format('Y-m-d H:i:s'),
            $plate->series_id,
            $plate->id,
            '"' . ($plate->name ?? 'unknown') . '"',
            $reason
        );
        file_put_contents(storage_path(self::LOG_FILE), $line, FILE_APPEND);
    }

    private function appendRunSummary(int $seriesId, int $processed, int $skipped, int $failed): void
    {
        $line = sprintf(
            "[%s] HEADER/FOOTER RUN COMPLETE  series=%d  processed=%d  skipped=%d  failed=%d\n",
            now()->format('Y-m-d H:i:s'),
            $seriesId,
            $processed,
            $skipped,
            $failed
        );
        file_put_contents(storage_path(self::LOG_FILE), $line, FILE_APPEND);
    }

    private function processPlate(Plate $plate, string $apiKey): string
    {
        $fn = preg_replace('#^plates/#', '', $plate->image_filename);
        $imagePath = Storage::disk('public')->path('plates/' . $fn);

        if (! file_exists($imagePath)) {
            $this->newLine();
            $this->warn("  Plate #{$plate->id} — image file not found: {$fn}");
            $this->logFailure($plate, "image file not found: {$fn}");

            return 'skip';
        }

        try {
            [$imageData, $mimeType] = $this->prepareImageForVision($imagePath);
        } catch (\Throwable $e) {
            $this->newLine();
            $this->warn("  Plate #{$plate->id} — could not read image: {$e->getMessage()}");
            $this->logFailure($plate, 'image read failed: ' . $e->getMessage());

            return 'error';
        }

        $regionName = $plate->series?->region?->name ?? 'Unknown';
        $regionCode = $plate->series?->region?->code ?? '';
        $plateName  = $plate->name ?? '';

        $prompt = $this->buildPrompt($regionName, $regionCode, $plateName);

        $attempts = 0;
        retry:
        $attempts++;

        try {
            $response = Http::withToken($apiKey)
                ->withoutVerifying()
                ->timeout(45)
                ->post('https://api.openai.com/v1/chat/completions', [
                    'model'           => 'gpt-4o',
                    'max_tokens'      => 300,
                    'response_format' => ['type' => 'json_object'],
                    'messages'        => [
                        [
                            'role'    => 'user',
                            'content' => [
                                [
                                    'type' => 'text',
                                    'text' => $prompt,
                                ],
                                [
                                    'type'      => 'image_url',
                                    'image_url' => [
                                        'url'    => "data:{$mimeType};base64,{$imageData}",
                                        'detail' => 'high',
                                    ],
                                ],
                            ],
                        ],
                    ],
                ]);

            if (! $response->successful()) {
                $msg = "API error {$response->status()}: {$response->body()}";
                $this->newLine();
                $this->error("  Plate #{$plate->id} — {$msg}");
                $this->logFailure($plate, $msg);

                return 'error';
            }

            $content = $response->json('choices.0.message.content');
            $parsed  = json_decode($content, true);

            if (! is_array($parsed) || ! array_key_exists('header', $parsed) || ! array_key_exists('footer', $parsed)) {
                if ($attempts < 2) {
                    sleep(3);
                    goto retry;
                }
                $msg = 'unexpected JSON: ' . ($content ?: '(empty response)');
                $this->newLine();
                $this->warn("  Plate #{$plate->id} — {$msg}");
                $this->logFailure($plate, $msg);

                return 'error';
            }

            try {
                $header = $this->normalizeField($parsed['header']);
                $footer = $this->normalizeField($parsed['footer']);
            } catch (\InvalidArgumentException $e) {
                $this->newLine();
                $this->warn("  Plate #{$plate->id} — {$e->getMessage()}");
                $this->logFailure($plate, $e->getMessage());

                return 'error';
            }

            $plate->update([
                'header_override'  => $header,
                'footer_override'  => $footer,
                'updates_complete' => true,
            ]);

            $this->newLine();
            $this->line(sprintf(
                '  Plate #%d — header=%s | footer=%s',
                $plate->id,
                $header === null ? 'NULL' : json_encode($header),
                $footer === null ? 'NULL' : json_encode($footer)
            ));

            unset($response, $content, $parsed, $imageData, $header, $footer);

            return 'ok';

        } catch (\Throwable $e) {
            unset($imageData);
            $this->newLine();
            $this->error("  Plate #{$plate->id} — exception: {$e->getMessage()}");
            $this->logFailure($plate, 'exception: ' . $e->getMessage());

            return 'error';
        }
    }

    private function normalizeField(mixed $value): ?string
    {
        if ($value === null) {
            return null;
        }

        if (! is_string($value)) {
            throw new \InvalidArgumentException('header/footer must be string or null');
        }

        $trimmed = trim($value);

        if ($trimmed === '' || strcasecmp($trimmed, 'null') === 0) {
            return null;
        }

        if (strlen($trimmed) > self::MAX_FIELD_LENGTH) {
            throw new \InvalidArgumentException('value exceeds ' . self::MAX_FIELD_LENGTH . ' characters');
        }

        return $trimmed;
    }

    /**
     * @return array{0: string, 1: string}
     */
    private function prepareImageForVision(string $imagePath): array
    {
        $mimeType = mime_content_type($imagePath) ?: 'image/jpeg';
        $fileSize = filesize($imagePath) ?: 0;
        $maxBytes = 350 * 1024;
        $maxEdge  = 1200;

        $needsResize = $fileSize > $maxBytes;

        if (! $needsResize && extension_loaded('gd')) {
            $info = @getimagesize($imagePath);
            if ($info && ($info[0] > $maxEdge || $info[1] > $maxEdge)) {
                $needsResize = true;
            }
        }

        if (! $needsResize || ! extension_loaded('gd')) {
            $raw = file_get_contents($imagePath);
            if ($raw === false) {
                throw new \RuntimeException('file_get_contents failed');
            }

            return [base64_encode($raw), $mimeType];
        }

        $source = $this->loadGdImage($imagePath, $mimeType);
        if ($source === false) {
            $raw = file_get_contents($imagePath);
            if ($raw === false) {
                throw new \RuntimeException('file_get_contents failed');
            }

            return [base64_encode($raw), $mimeType];
        }

        $width  = imagesx($source);
        $height = imagesy($source);
        $scale  = min($maxEdge / $width, $maxEdge / $height, 1.0);
        $newW   = max(1, (int) round($width * $scale));
        $newH   = max(1, (int) round($height * $scale));

        $resized = imagescale($source, $newW, $newH, IMG_BILINEAR_FIXED);
        imagedestroy($source);

        if ($resized === false) {
            throw new \RuntimeException('imagescale failed');
        }

        ob_start();
        imagejpeg($resized, null, 85);
        imagedestroy($resized);
        $jpeg = ob_get_clean();

        if ($jpeg === false || $jpeg === '') {
            throw new \RuntimeException('jpeg encode failed');
        }

        return [base64_encode($jpeg), 'image/jpeg'];
    }

    private function loadGdImage(string $imagePath, string $mimeType): \GdImage|false
    {
        return match ($mimeType) {
            'image/jpeg', 'image/jpg' => @imagecreatefromjpeg($imagePath),
            'image/png'               => @imagecreatefrompng($imagePath),
            'image/gif'               => @imagecreatefromgif($imagePath),
            'image/webp'              => function_exists('imagecreatefromwebp') ? @imagecreatefromwebp($imagePath) : false,
            default                   => @imagecreatefromstring((string) file_get_contents($imagePath)),
        };
    }

    private function buildPrompt(string $regionName, string $regionCode, string $plateName): string
    {
        $regionHint = trim($regionName . ($regionCode !== '' ? " ({$regionCode})" : ''));

        return <<<PROMPT
IMPORTANT — READ FIRST: Some plate template images contain the word "SAMPLE" printed
as a large watermark. This word does not exist on any real plate. Treat "SAMPLE" as
completely invisible — never include it in header or footer.

Context hints (for geography only — DO NOT copy these strings into header or footer):
- Region: {$regionHint}
- Plate catalog name: "{$plateName}"

The catalog name is an admin label (e.g. "GA - Cobb County Humane Society"). It is
NOT the footer. The actual footer might be slogan text on the plate graphic such as
"Spay * Neuter * Adopt". Read header and footer ONLY from visible text on the image.

Your task: extract HEADER and FOOTER text from this license plate template image.

Return JSON with exactly two keys:
- header: string or null
- footer: string or null

HEADER zone — upper center band of the plate:
- Usually the state, province, or country name (e.g. Vermont, Quebec, New Mexico USA).
- null if there is no intentional text in the upper-center header band.

FOOTER zone — lower portion of the plate (bottom-center and nearby lower text):
- May include: state/province name (South Carolina often puts the state name HERE,
  not in the header), slogans, plate-type labels, commemorative text.
- On crowded plates, designation text printed BELOW the serial number but above the
  bottom edge is still FOOTER (e.g. "Pearl Harbor Survivor" below stacked PHS/000,
  with "New Mexico USA" at the very bottom — combine as footer using | top-to-bottom:
  "Pearl Harbor Survivor|New Mexico USA").
- null if there is no intentional footer text.

Multi-line text within one field: join lines top-to-bottom with | (pipe), no spaces
around the pipe unless they appear on the plate.

IGNORE completely (never put in header or footer):
- Serial / registration numbers (center digits and letters)
- Stacked org codes middle-left of serial (e.g. PHS, AW, DP, WW)
- Middle-center registration area
- Sticker placement labels: "PLACE STICKER HERE", "Place Year Sticker Here",
  "TAB HERE", "MONTH", "YEAR", barcode strips
- The word SAMPLE (watermark)

Rules:
1) Preserve exact letter case as printed on the plate.
2) Never copy the catalog plate name into header or footer unless that exact text
   is visibly printed in that zone on the image.
3) Blackout / retro plates may have only a state name — one field may be filled,
   the other null.
4) Every plate has some geopolitical identifier somewhere; it may be in header OR
   footer depending on the state design.
5) Output valid JSON only — no markdown, no explanation.
PROMPT;
    }
}
