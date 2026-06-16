<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Purchase;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class PurchaseController extends Controller
{
    /**
     * Verify an in-app purchase server-to-server via RevenueCat subscriber lookup,
     * then grant the authenticated user full (premium) access.
     *
     * POST /api/v1/auth/purchase/verify
     *
     * Expected body:
     *   platform       string  "apple" or "google" — never "founding" or "stripe"
     *   transaction_id string  The RevenueCat transaction identifier (used for deduplication)
     *   product_id     string  The product identifier (e.g. com.platetag.mobile.full)
     *
     * The RevenueCat SDK syncs the transaction to RevenueCat servers before this is called.
     * Verification is done by querying GET /v1/subscribers/{app_user_id} — no raw receipt needed.
     */
    public function verify(Request $request): JsonResponse
    {
        $data = $request->validate([
            // 'founding' and 'stripe' are NEVER accepted from client input.
            // 'founding' is set server-side at registration. 'stripe' is handled via webhook (future).
            'platform'       => ['required', 'string', 'in:apple,google'],
            'transaction_id' => ['required', 'string', 'max:255'],
            'product_id'     => ['required', 'string', 'max:255'],
        ]);

        // Whitelist product_id against known valid products.
        // This prevents a client from sending a trial or free product ID to obtain premium access.
        $allowedProductIds = array_filter(
            array_map('trim', explode(',', config('services.revenuecat.product_ids', '')))
        );
        if (app()->environment('production') && empty($allowedProductIds)) {
            Log::error('Purchase verify blocked: REVENUECAT_PRODUCT_IDS is empty in production', [
                'user_id' => $request->user()->id,
            ]);
            return response()->json([
                'message' => 'Purchases are temporarily unavailable. Please try again later.',
            ], 503);
        }
        if (! empty($allowedProductIds) && ! in_array($data['product_id'], $allowedProductIds, true)) {
            Log::warning('Purchase verify: unknown product_id rejected', [
                'user_id'    => $request->user()->id,
                'product_id' => $data['product_id'],
            ]);
            return response()->json([
                'message' => 'Purchase could not be verified. Please try again or contact support.',
            ], 422);
        }

        $user = $request->user();

        // Check for an existing purchase with this transaction_id + platform.
        // The unique constraint covers (transaction_id, platform) to prevent cross-platform
        // ID collisions from accidentally matching.
        $existing = Purchase::where('transaction_id', $data['transaction_id'])
            ->where('platform', $data['platform'])
            ->first();

        if ($existing) {
            if ($existing->user_id === $user->id) {
                // Same user, same transaction — idempotent success.
                // This is the normal path for "Restore Purchases" taps.
                return response()->json([
                    'message'    => 'Purchase already verified.',
                    'is_premium' => true,
                ]);
            }
            // Different user claiming the same transaction — reject.
            // Could indicate transaction sharing or a replay attack.
            Log::warning('Purchase verify: transaction_id claimed by a different user', [
                'transaction_id'    => $data['transaction_id'],
                'platform'          => $data['platform'],
                'requesting_user'   => $user->id,
                'existing_owner'    => $existing->user_id,
            ]);
            return response()->json([
                'message' => 'This transaction has already been used on a different account.',
            ], 422);
        }

        // Validate server-to-server with RevenueCat subscriber lookup.
        // We never trust the client's own claim that a purchase succeeded.
        $validation = $this->validateWithRevenueCat($user->id);

        if (! $validation['valid']) {
            Log::warning('RevenueCat validation failed', [
                'user_id'  => $user->id,
                'platform' => $data['platform'],
                'reason'   => $validation['reason'] ?? 'unknown',
            ]);
            return response()->json([
                'message' => 'Purchase could not be verified. Please try again or contact support.',
            ], 422);
        }

        // Store the purchase record and grant premium atomically.
        // The UniqueConstraintViolationException catch handles the narrow race condition where
        // two simultaneous requests for the same transaction_id both pass the pre-check above
        // and then race to insert. The first wins; the second hits the DB unique constraint.
        // In that case, premium was already granted by the winner — return idempotent success.
        try {
            DB::transaction(function () use ($user, $data) {
                Purchase::create([
                    'user_id'        => $user->id,
                    'platform'       => $data['platform'],
                    'product_id'     => $data['product_id'],
                    'transaction_id' => $data['transaction_id'],
                    'raw_receipt'    => null, // not used: verification via subscriber lookup
                    'verified_at'    => now(),
                ]);

                // forceFill() is required — is_premium is intentionally excluded from $fillable
                // to prevent mass assignment attacks. This is the only place it is set for purchases.
                $user->forceFill([
                    'is_premium'         => true,
                    'premium_granted_at' => now(),
                ])->save();
            });
        } catch (UniqueConstraintViolationException) {
            // Lost the race — another concurrent request already verified and inserted this
            // transaction. The premium grant from that request is already applied.
            return response()->json([
                'message'    => 'Purchase already verified.',
                'is_premium' => true,
            ]);
        }

        return response()->json([
            'message'    => 'Purchase verified. Welcome to PlateTag Full!',
            'is_premium' => true,
        ]);
    }

    /**
     * Query RevenueCat's GET /v1/subscribers/{app_user_id} endpoint to confirm
     * the user has an active entitlement. The RevenueCat SDK syncs the transaction
     * to RevenueCat servers before this is called — no raw receipt is needed.
     *
     * Rejects sandbox entitlements when APP_ENV=production.
     */
    private function validateWithRevenueCat(int $userId): array
    {
        $secretKey     = config('services.revenuecat.secret_key');
        $entitlementId = config('services.revenuecat.entitlement_id', 'full_access');

        if (! $secretKey) {
            Log::error('REVENUECAT_SECRET_KEY is not configured');
            return ['valid' => false, 'reason' => 'RevenueCat not configured'];
        }

        $response = Http::timeout(10)->withHeaders([
            'Authorization' => 'Bearer ' . $secretKey,
            'Content-Type'  => 'application/json',
        ])->get('https://api.revenuecat.com/v1/subscribers/' . $userId);

        if (! $response->successful()) {
            return [
                'valid'  => false,
                'reason' => 'RevenueCat API returned HTTP ' . $response->status(),
            ];
        }

        $body       = $response->json();
        $subscriber = $body['subscriber'] ?? null;

        if (! $subscriber) {
            return ['valid' => false, 'reason' => 'No subscriber object in RevenueCat response'];
        }

        // Confirm the target entitlement exists and is not expired.
        $entitlements = $subscriber['entitlements'] ?? [];
        $entitlement  = $entitlements[$entitlementId] ?? null;

        if (! $entitlement) {
            return ['valid' => false, 'reason' => "Entitlement '{$entitlementId}' not found"];
        }

        // expires_date is null for lifetime/one-time purchases — that is a valid active state.
        if (
            $entitlement['expires_date'] !== null &&
            \Carbon\Carbon::parse($entitlement['expires_date'])->isPast()
        ) {
            return ['valid' => false, 'reason' => "Entitlement '{$entitlementId}' is expired"];
        }

        // In production, reject sandbox entitlements to prevent abuse.
        if (app()->environment('production')) {
            $nonSubscriptions = $subscriber['non_subscriptions'] ?? [];
            foreach ($nonSubscriptions as $transactions) {
                foreach ($transactions as $tx) {
                    if (($tx['is_sandbox'] ?? false) === true) {
                        return ['valid' => false, 'reason' => 'Sandbox purchase rejected in production'];
                    }
                }
            }
        }

        return ['valid' => true];
    }
}
