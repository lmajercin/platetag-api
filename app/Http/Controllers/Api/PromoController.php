<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\PromoCode;
use App\Models\PromoCodeRedemption;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

class PromoController extends Controller
{
    /**
     * Redeem a promo code for the authenticated user.
     *
     * POST /api/v1/auth/promo/redeem
     *
     * Expected body:
     *   code  string  The promo code (case-insensitive; normalized to uppercase internally)
     *
     * Security notes:
     * - Rate limited to throttle:auth (10/min) to mitigate brute-force guessing.
     * - Codes must be minimum 8 characters (enforced in Filament + this validation rule).
     * - is_premium and promo_expires_at are set via forceFill() — never in $fillable.
     * - lockForUpdate() on the promo_codes row prevents the max_uses race condition.
     * - (promo_code_id, user_id) unique index + UniqueConstraintViolationException catch
     *   provides a DB-level backstop against concurrent same-user redemption.
     */
    public function redeem(Request $request): JsonResponse
    {
        $data = $request->validate([
            // Minimum 8 chars, uppercase alphanumeric + hyphens only.
            // Audit required this to prevent brute-force and injection.
            'code' => ['required', 'string', 'max:32', 'regex:/^[A-Z0-9\-]{8,32}$/i'],
        ], [
            'code.required' => 'Please enter a promo code.',
            'code.max'      => 'That code is too long.',
            'code.regex'    => 'Promo codes use letters, numbers, and hyphens only.',
        ]);

        // Normalize before any DB query — compare against uppercase stored values.
        $normalizedCode = strtoupper(trim($data['code']));

        $user = $request->user();

        // If the user already has permanent premium (paid IAP, not windowed promo),
        // return idempotent success without consuming a redemption slot.
        // Windowed promo users (is_premium=true, promo_expires_at set) CAN redeem
        // another code to extend or replace their access.
        if ($user->is_premium && $user->promo_expires_at === null && ! $user->promoRedemptions()->exists()) {
            return response()->json([
                'message'          => 'Your account already has full access.',
                'is_premium'       => true,
                'promo_expires_at' => null,
            ]);
        }

        try {
            $result = DB::transaction(function () use ($user, $normalizedCode) {
                // lockForUpdate() acquires an exclusive row lock before ANY validation checks.
                // This prevents the TOCTOU race on max_uses: two concurrent requests both
                // passing the check before either inserts. Only one request holds the lock at a time.
                $code = PromoCode::where('code', $normalizedCode)
                    ->where('is_active', true)
                    ->lockForUpdate()
                    ->first();

                if (! $code) {
                    // Unified error — do not distinguish "not found" from "inactive."
                    return ['error' => 'invalid', 'status' => 422];
                }

                // Timing and capacity checks INSIDE the lock.
                $now = now();

                if ($code->starts_at > $now) {
                    return ['error' => 'invalid', 'status' => 422];
                }

                if ($code->expires_at !== null && $code->expires_at < $now) {
                    return ['error' => 'invalid', 'status' => 422];
                }

                if ($code->max_uses !== null && $code->uses_count >= $code->max_uses) {
                    return ['error' => 'invalid', 'status' => 422];
                }

                // Check if this user already redeemed this specific code.
                if (PromoCodeRedemption::where('promo_code_id', $code->id)
                    ->where('user_id', $user->id)
                    ->exists()) {
                    // Idempotent — same user, same code. Return success without double-counting.
                    return ['already_redeemed' => true, 'code' => $code];
                }

                // Insert the redemption record.
                PromoCodeRedemption::create([
                    'promo_code_id' => $code->id,
                    'user_id'       => $user->id,
                    'redeemed_at'   => $now,
                ]);

                // Atomic increment — issues UPDATE promo_codes SET uses_count = uses_count + 1
                $code->increment('uses_count');

                // Determine the user access expiry.
                // If the code itself has an expires_at, that date is when the user's access ends.
                // If the code has no expires_at (permanent code), the user gets permanent access.
                $promoExpiresAt = $code->expires_at;

                // forceFill() — is_premium and promo_expires_at are excluded from $fillable.
                $user->forceFill([
                    'is_premium'       => true,
                    'premium_granted_at' => $now,
                    'promo_expires_at' => $promoExpiresAt,
                ])->save();

                return ['success' => true, 'promo_expires_at' => $promoExpiresAt];
            });

        } catch (UniqueConstraintViolationException) {
            // The (promo_code_id, user_id) unique index fired — a concurrent request
            // for the same user + code already inserted. Treat as idempotent success.
            $user->refresh();
            return response()->json([
                'message'          => 'Promo code applied.',
                'is_premium'       => true,
                'promo_expires_at' => $user->promo_expires_at?->toISOString(),
            ]);
        }

        // Handle error results from the transaction closure.
        if (isset($result['error'])) {
            return response()->json([
                'message' => 'Invalid or expired code.',
            ], $result['status']);
        }

        // Idempotent re-redemption of the same code by the same user.
        if (isset($result['already_redeemed'])) {
            $user->refresh();
            return response()->json([
                'message'          => 'Promo code already applied to your account.',
                'is_premium'       => true,
                'promo_expires_at' => $user->promo_expires_at?->toISOString(),
            ]);
        }

        // Success.
        Log::info('Promo code redeemed', [
            'user_id'          => $user->id,
            'promo_expires_at' => $result['promo_expires_at'],
        ]);

        return response()->json([
            'message'          => 'Promo code applied. Enjoy PlateTag Full!',
            'is_premium'       => true,
            'promo_expires_at' => $result['promo_expires_at']?->toISOString(),
        ]);
    }
}
