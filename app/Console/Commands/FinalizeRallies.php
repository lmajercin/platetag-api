<?php

namespace App\Console\Commands;

use App\Models\Game;
use App\Models\Group;
use App\Models\UserDevice;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

// @Audit GO: 2026-10-27 — Build 91 (5b).
// Midnight scheduler: auto-finalize expired Road Rallies and push-notify group members.
// - Calls Game::finalizeRally() (shared with GameController::finalize() — no auth bypass).
// - Per-rally DB::transaction() + lockForUpdate() prevents race with manual finalization.
// - Synchronous push send (no queue worker on A2). Chunked ≤100 per Expo API call.
// - DeviceNotRegistered response deletes stale token from user_devices.
// - Per-token try/catch: one failed token never aborts the batch.

class FinalizeRallies extends Command
{
    protected $signature   = 'rallies:finalize';
    protected $description = 'Auto-finalize expired Road Rallies and push-notify group members.';

    // Expo Push API endpoint
    private const EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send';

    public function handle(): int
    {
        // Find active Road Rallies whose end_date has passed
        $expiredGames = Game::where('type', 'road_rally')
            ->where('status', 'active')
            ->where('end_date', '<', now())
            ->get();

        if ($expiredGames->isEmpty()) {
            $this->info('No expired rallies to finalize.');
            return self::SUCCESS;
        }

        $finalized = 0;
        $skipped   = 0;

        foreach ($expiredGames as $game) {
            try {
                $result = DB::transaction(function () use ($game) {
                    // lockForUpdate: prevents race with manual finalize by leader
                    $locked = Game::where('id', $game->id)
                        ->where('status', 'active')   // re-check inside lock
                        ->lockForUpdate()
                        ->first();

                    if (! $locked) {
                        return null; // Already finalized between query and lock
                    }

                    $locked->finalizeRally();

                    Log::info('rallies:finalize — finalized', [
                        'game_id'  => $locked->id,
                        'group_id' => $locked->group_id,
                    ]);

                    return $locked;
                });

                if ($result === null) {
                    $skipped++;
                    continue;
                }

                $finalized++;

                // Notify group members
                $this->notifyGroupMembers($result);

            } catch (\Throwable $e) {
                // One failed rally never aborts the batch
                Log::error('rallies:finalize — error finalizing game', [
                    'game_id' => $game->id,
                    'error'   => $e->getMessage(),
                ]);
                $this->error("Game {$game->id} failed: {$e->getMessage()}");
            }
        }

        $this->info("Finalized: {$finalized} | Skipped (already done): {$skipped}");

        return self::SUCCESS;
    }

    /**
     * Push-notify all members of the group that the rally has ended.
     * Chunks ≤100 per Expo API request. Cleans up DeviceNotRegistered tokens.
     */
    private function notifyGroupMembers(Game $game): void
    {
        $group = Group::with('members')->findOrFail($game->group_id);
        $memberIds = $group->members->pluck('user_id')->toArray();

        if (empty($memberIds)) {
            return;
        }

        $tokens = UserDevice::whereIn('user_id', $memberIds)
            ->pluck('push_token', 'push_token') // keyed by token for stale-cleanup
            ->keys()
            ->toArray();

        if (empty($tokens)) {
            // No tokens yet — expected until users install Build 91
            Log::info('rallies:finalize — no push tokens for group', ['group_id' => $game->group_id]);
            return;
        }

        $payload = collect($tokens)->map(fn($token) => [
            'to'    => $token,
            'title' => "Road Rally Ended — {$group->name}",
            'body'  => 'The rally has finished! Tap to see the final results.',
            'data'  => ['group_id' => $game->group_id, 'game_id' => $game->id],
        ])->values()->toArray();

        // Chunk ≤100 per Expo API call (documented rate limit)
        foreach (array_chunk($payload, 100) as $chunk) {
            try {
                $response = Http::timeout(10)->post(self::EXPO_PUSH_URL, $chunk);
                $body     = $response->json();

                // Inspect per-token results for DeviceNotRegistered
                foreach ($body['data'] ?? [] as $i => $result) {
                    if (($result['status'] ?? '') === 'error'
                        && ($result['details']['error'] ?? '') === 'DeviceNotRegistered') {
                        $staleToken = $chunk[$i]['to'] ?? null;
                        if ($staleToken) {
                            UserDevice::where('push_token', $staleToken)->delete();
                            Log::info('rallies:finalize — stale token removed', ['token' => substr($staleToken, 0, 20)]);
                        }
                    }
                }
            } catch (\Throwable $e) {
                // Network failure for one chunk — log and continue
                Log::error('rallies:finalize — Expo push send failed', [
                    'group_id' => $game->group_id,
                    'error'    => $e->getMessage(),
                ]);
            }
        }
    }
}
