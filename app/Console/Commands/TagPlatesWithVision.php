<?php

namespace App\Console\Commands;

use App\Models\Plate;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

class TagPlatesWithVision extends Command
{
    protected $signature = 'tagger:run
                            {--limit=0 : Maximum number of plates to process (0 = all eligible)}
                            {--plate=0 : Process a single plate by ID}
                            {--force   : Re-process plates that already have ai_detail}';

    protected $description = 'Tag plates with GPT-4o Vision — writes drafts to ai_detail and ai_tags only. Never overwrites detail or tags.';

    public function handle(): int
    {
        $apiKey = config('services.openai.key');

        if (empty($apiKey)) {
            $this->error('OPENAI_API_KEY is not set. Add it to .env and try again.');
            return self::FAILURE;
        }

        $query = Plate::with('series.region')
            ->whereNotNull('image_filename')
            ->where('image_filename', '!=', '');

        if ($this->option('plate')) {
            $query->where('id', (int) $this->option('plate'));
        } else {
            // Eligibility: only plates where BOTH detail and tags are empty
            $query->where(fn ($q) => $q->whereNull('detail')->orWhere('detail', ''))
                  ->where(fn ($q) => $q->whereNull('tags')->orWhere('tags', ''));

            if (! $this->option('force')) {
                // Skip plates already sitting in the Filament review queue (draft, not yet approved).
                // Plates cleared back into the queue (empty detail/tags, ai_reviewed=true) stay eligible.
                $query->where(function ($q) {
                    $q->where(fn ($q2) => $q2->whereNull('ai_detail')->orWhere('ai_detail', ''))
                      ->orWhere('ai_reviewed', true);
                });
            }

            // Always process lowest id first so re-queued plates are picked up before newer work.
            $query->orderBy('id');

            if ($this->option('limit') > 0) {
                $query->limit((int) $this->option('limit'));
            }
        }

        $plates = $query->get();

        if ($plates->isEmpty()) {
            $this->info('No eligible plates found.');
            return self::SUCCESS;
        }

        $this->info("Processing {$plates->count()} plate(s)...");

        $processed = 0;
        $skipped   = 0;
        $failed    = 0;

        $bar = $this->output->createProgressBar($plates->count());
        $bar->start();

        foreach ($plates as $plate) {
            $result = $this->processPlate($plate, $apiKey);

            match ($result) {
                'ok'      => $processed++,
                'skip'    => $skipped++,
                default   => $failed++,
            };

            $bar->advance();

            // Throttle: 1 request per second to stay within OpenAI rate limits
            if ($processed + $failed < $plates->count()) {
                sleep(1);
            }
        }

        $bar->finish();
        $this->newLine(2);
        $this->table(
            ['Processed', 'Skipped', 'Failed'],
            [[$processed, $skipped, $failed]]
        );

        $this->appendRunSummary($processed, $skipped, $failed);

        return self::SUCCESS;
    }

    private function logFailure(Plate $plate, string $reason): void
    {
        $line = sprintf(
            "[%s] FAILED  Plate #%-6d  %-50s  %s\n",
            now()->format('Y-m-d H:i:s'),
            $plate->id,
            '"' . ($plate->name ?? 'unknown') . '"',
            $reason
        );
        file_put_contents(storage_path('logs/tagger-failures.log'), $line, FILE_APPEND);
    }

    private function appendRunSummary(int $processed, int $skipped, int $failed): void
    {
        $line = sprintf(
            "[%s] RUN COMPLETE  processed=%d  skipped=%d  failed=%d\n",
            now()->format('Y-m-d H:i:s'),
            $processed,
            $skipped,
            $failed
        );
        file_put_contents(storage_path('logs/tagger-failures.log'), $line, FILE_APPEND);

        if ($failed > 0) {
            $this->line('  Failures logged to: storage/logs/tagger-failures.log');
        }
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

        $imageData = base64_encode(file_get_contents($imagePath));
        $mimeType  = mime_content_type($imagePath) ?: 'image/jpeg';

        $regionName = $plate->series?->region?->name ?? 'Unknown';
        $plateName  = $plate->name ?? '';

        $prompt = $this->buildPrompt($regionName, $plateName);

        $attempts = 0;
        retry:
        $attempts++;

        try {
            $response = Http::withToken($apiKey)
                ->withoutVerifying() // WAMP/Windows has no CA bundle — local-only command, safe to skip
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

            $plate->update([
                'ai_detail'   => trim($parsed['detail']),
                'ai_tags'     => trim($parsed['tags']),
                'ai_reviewed' => false,
            ]);

            return 'ok';

        } catch (\Throwable $e) {
            $this->newLine();
            $this->error("  Plate #{$plate->id} — exception: {$e->getMessage()}");
            $this->logFailure($plate, 'exception: ' . $e->getMessage());
            return 'error';
        }
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
