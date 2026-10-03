<?php

namespace App\Console\Commands;

use App\Models\Plate;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

class TagPlatesWithVisionBulk extends Command
{
    protected $signature = 'tagger:bulk-series
                            {series : Series ID to process (e.g. 721)}
                            {--limit=0 : Maximum plates to process (0 = all eligible in series)}
                            {--plate=0 : Process a single plate by ID (must belong to the series)}
                            {--dry-run : List eligible plates only — no OpenAI calls, no DB writes}';

    protected $description = 'Bulk GPT-4o Vision tagger by series — writes ai_detail, detail, ai_tags, tags, and sets ai_reviewed=1. Skips any plate with existing content or ai_reviewed=1. Local WAMP only.';

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

        $this->info("Bulk tagger — series {$seriesId}: processing {$total} plate(s)...");
        $this->warn('Auto-approve ON: detail, tags, ai_detail, ai_tags will be written; ai_reviewed set to 1.');

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
            $this->line('  Failures logged to: storage/logs/tagger-bulk-failures.log');
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

    /**
     * Only completely untouched plates: all four text fields empty AND ai_reviewed not set.
     */
    private function applyEligibilityScope($query): void
    {
        $query->where(fn ($q) => $q->whereNull('detail')->orWhere('detail', ''))
              ->where(fn ($q) => $q->whereNull('ai_detail')->orWhere('ai_detail', ''))
              ->where(fn ($q) => $q->whereNull('tags')->orWhere('tags', ''))
              ->where(fn ($q) => $q->whereNull('ai_tags')->orWhere('ai_tags', ''))
              ->where('ai_reviewed', false);
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
            $plate->detail ? 'set' : 'empty',
            $plate->ai_detail ? 'set' : 'empty',
            $plate->tags ? 'set' : 'empty',
            $plate->ai_tags ? 'set' : 'empty',
            $plate->ai_reviewed ? '1' : '0',
            preg_replace('#^plates/#', '', $plate->image_filename ?? ''),
        ])->all();

        $this->table(['ID', 'Name', 'detail', 'ai_detail', 'tags', 'ai_tags', 'ai_reviewed', 'image'], $rows);

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
        file_put_contents(storage_path('logs/tagger-bulk-failures.log'), $line, FILE_APPEND);
    }

    private function appendRunSummary(int $seriesId, int $processed, int $skipped, int $failed): void
    {
        $line = sprintf(
            "[%s] BULK RUN COMPLETE  series=%d  processed=%d  skipped=%d  failed=%d\n",
            now()->format('Y-m-d H:i:s'),
            $seriesId,
            $processed,
            $skipped,
            $failed
        );
        file_put_contents(storage_path('logs/tagger-bulk-failures.log'), $line, FILE_APPEND);
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
        $plateName  = $plate->name ?? '';

        $prompt = $this->buildPrompt($regionName, $plateName);

        $attempts = 0;
        retry:
        $attempts++;

        try {
            $response = Http::withToken($apiKey)
                ->withoutVerifying()
                ->timeout(30)
                ->post('https://api.openai.com/v1/chat/completions', [
                    'model'           => 'gpt-4o',
                    'max_tokens'      => 500,
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
                                        'detail' => 'low',
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

            if (! isset($parsed['detail'], $parsed['tags'])) {
                if ($attempts < 2) {
                    sleep(3);
                    goto retry;
                }
                $msg = 'unexpected JSON: ' . ($content ?: '(empty response — possible content filter or unsupported image format)');
                $this->newLine();
                $this->warn("  Plate #{$plate->id} — {$msg}");
                $this->logFailure($plate, $msg);
                return 'error';
            }

            $detail = trim($parsed['detail']);
            $tags   = trim($parsed['tags']);

            $plate->update([
                'ai_detail'   => $detail,
                'ai_tags'     => $tags,
                'detail'      => $detail,
                'tags'        => $tags,
                'ai_reviewed' => true,
            ]);

            unset($response, $content, $parsed, $imageData, $detail, $tags);

            return 'ok';

        } catch (\Throwable $e) {
            unset($imageData);
            $this->newLine();
            $this->error("  Plate #{$plate->id} — exception: {$e->getMessage()}");
            $this->logFailure($plate, 'exception: ' . $e->getMessage());
            return 'error';
        }
    }

    /**
     * Return [base64, mimeType]. Large images are downscaled to reduce memory and API failures.
     *
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

    private function buildPrompt(string $regionName, string $plateName): string
    {
        return <<<PROMPT
IMPORTANT — READ FIRST: Some plate template images contain the word "SAMPLE" printed
as a large watermark. This word does not exist on any real plate. If you see "SAMPLE"
anywhere in the image, treat it as completely invisible. Do not mention it in detail,
do not include it in tags, do not acknowledge its presence in any way.

This is a {$regionName} license plate graphic. The plate is named "{$plateName}".

Your task is to describe the DESIGN of this plate type — treat it as a template,
not an individual vehicle's plate.

Return JSON with exactly two keys:
- detail: 1-2 sentence visual description of the plate design including base
  color, text layout, colors, symbols, imagery, and theme. Start directly with
  the visual description — do NOT open with "license plate", the plate name, or
  the state name (e.g. start with "Cream base with..." not "The Pennsylvania
  Eastern Hellbender license plate features a cream background...").
  Use "base" (not "background") when referring to the plate's primary color or
  surface. Reserve "background" only for depth within artwork (e.g. "mountains
  in the background of the scene").
- tags: comma-separated list of 15-20 search keywords. Always include
  "{$regionName}" as a tag.

Rules:
1) The state/region is {$regionName} — do not identify it as any other state.
2) IGNORE the serial number completely. The registration number printed on this
   specific plate is not part of the design. Do not describe its value, size,
   color, position, or presence anywhere in detail or tags.
3) NEVER mention registration sticker wells, sticker areas, or corner wells —
   not in detail, not in tags, under any circumstances.
4) IGNORE image defects: damage, bends, scratches, lens flare, shadows, or
   photographic artifacts. Describe only the plate's intended design.
5) Include all intentional plate text: header, footer, slogans, state name,
   plate type label. NOTE: stacked letters to the left of the serial number
   (such as "QUE") are an intentional organization identifier — include them.
   EXCEPTION: The word "SAMPLE" is never intentional plate text — it is always
   a watermark on a template image. Treat it as invisible. Do not include it
   in detail or tags under any circumstances.
6) Include visual design elements: animals, scenery, colors, symbols, emblems,
   artwork. Pay specific attention to accessibility symbols: the International
   Symbol of Access (blue or white wheelchair figure) is a distinct design
   element — always identify and include it when present. It is NOT part of
   the serial number even if it appears between alphanumeric characters.
7) Use the plate name "{$plateName}" to correctly identify specific emblems or
   symbols that may be small or unclear in the image (e.g. if the name says
   "Purple Heart", identify the medal as a Purple Heart medal, not a generic emblem).
8) Output valid JSON only — no markdown, no explanation.
9) Background style tags: if the plate base is predominantly black, include
   "blackout" and "blackout plate" in the tags. Do NOT add any equivalent
   tag for white plates.
10) IGNORE any text that reads "TAB HERE", "MONTH", "YEAR", or similar
    registration sticker placement labels — these are not part of the design.
    CRITICAL: The word "SAMPLE" is a watermark only — it NEVER appears on a
    real plate. Do not mention "SAMPLE" anywhere in detail or tags under any
    circumstances.
11) Preserve exact letter case for all plate text exactly as it appears on the
    plate. Copy character-for-character: if the plate shows "DW", write "DW" —
    not "Dw" or "dw". If it shows "MONTANA", write "MONTANA".
PROMPT;
    }
}
