<?php

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

class ExpirePromoAccess extends Command
{
    protected $signature   = 'promo:expire-access';
    protected $description = 'Revoke is_premium for users whose windowed promo access has expired and who have no active IAP purchase.';

    public function handle(): int
    {
        // Find users where:
        //   - promo_expires_at is in the past (windowed access has lapsed)
        //   - is_premium is still true (access has not already been revoked)
        //   - no row in purchases (no paid IAP that should protect their premium status)
        //
        // We do NOT revoke users who:
        //   - have promo_expires_at = null (permanent promo or paid purchase — leave them alone)
        //   - have a row in purchases (paid access should never be revoked by this command)

        $expiredUsers = User::where('is_premium', true)
            ->whereNotNull('promo_expires_at')
            ->where('promo_expires_at', '<', now())
            ->whereDoesntHave('purchases')
            ->get();

        if ($expiredUsers->isEmpty()) {
            $this->info('No expired promo access to revoke.');
            return self::SUCCESS;
        }

        $count = 0;

        foreach ($expiredUsers as $user) {
            DB::transaction(function () use ($user) {
                $user->forceFill([
                    'is_premium'       => false,
                    'promo_expires_at' => null,
                ])->save();
            });

            Log::info('Promo access expired and revoked', [
                'user_id'          => $user->id,
                'promo_expires_at' => $user->promo_expires_at,
            ]);

            $count++;
        }

        $this->info("Revoked promo access for {$count} user(s).");

        return self::SUCCESS;
    }
}
