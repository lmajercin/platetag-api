<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Symfony\Component\HttpFoundation\Response;

/**
 * CheckPlayIntegrity
 *
 * Reads the X-Play-Integrity-Token header on high-risk endpoints (purchase verify,
 * promo redeem) and calls the Google Play Integrity API to decode the verdict.
 *
 * V1 POLICY — FAIL OPEN:
 * - Header absent (iOS, unknown platform): log and allow. Never block.
 * - Header present but API call fails (network error, timeout): log and allow.
 * - Header present and API returns low/unevaluated verdict: log warning and allow.
 * - Header present and API returns MEETS_DEVICE_INTEGRITY or better: log and allow.
 *
 * Hard-blocking is NOT enabled in v1. Enable only after 30+ days of verdict data
 * confirms the false-positive rate is acceptable. See APP_STATUS.md backlog.
 *
 * NONCE: V1 logging only — the nonce embedded in the token is NOT verified against
 * a server-issued challenge. This is a documented known gap. Replay protection
 * via server-issued one-time nonces is a post-launch v2 item.
 *
 * HTTP TIMEOUT: 5 seconds hard cap on the Google API call. On A2 shared hosting,
 * an unresponsive external API would otherwise hold a PHP worker open indefinitely.
 * If the call times out, we fail open and log integrity_api_timeout.
 */
class CheckPlayIntegrity
{
    public function handle(Request $request, Closure $next): Response
    {
        $token    = $request->header('X-Play-Integrity-Token');
        $endpoint = $request->path();
        $userId   = $request->user()?->id;

        if (! $token) {
            // No token — iOS client or integrity SDK unavailable.
            Log::info('play_integrity: skipped', [
                'user_id'  => $userId,
                'endpoint' => $endpoint,
                'platform' => 'unknown/ios',
            ]);
            return $next($request);
        }

        $package     = config('services.play_integrity.package');
        $credentials = $this->loadCredentials();

        if (! $package || ! $credentials) {
            // Env vars not configured — skip silently (local dev / mis-configured staging).
            Log::warning('play_integrity: env not configured', [
                'user_id'  => $userId,
                'endpoint' => $endpoint,
            ]);
            return $next($request);
        }

        try {
            $accessToken = $this->getGoogleAccessToken($credentials);

            $response = Http::timeout(5)
                ->withToken($accessToken)
                ->post(
                    "https://playintegrity.googleapis.com/v1/{$package}:decodeIntegrityToken",
                    ['integrity_token' => $token]
                );

            if (! $response->successful()) {
                Log::warning('play_integrity: api_error', [
                    'user_id'  => $userId,
                    'endpoint' => $endpoint,
                    'status'   => $response->status(),
                ]);
                return $next($request);
            }

            $payload = $response->json();

            // Verify package name (defense-in-depth).
            $tokenPackage = data_get($payload, 'tokenPayloadExternal.requestDetails.requestPackageName');
            if ($tokenPackage && $tokenPackage !== $package) {
                Log::warning('play_integrity: package_mismatch', [
                    'user_id'        => $userId,
                    'endpoint'       => $endpoint,
                    'token_package'  => $tokenPackage,
                    'expected'       => $package,
                ]);
                // Fail open — do not block, but log for investigation.
                return $next($request);
            }

            // Extract verdict enums only — do NOT log full accountDetails.
            $appVerdict    = data_get($payload, 'tokenPayloadExternal.appIntegrity.appRecognitionVerdict', 'UNEVALUATED');
            $deviceVerdict = data_get($payload, 'tokenPayloadExternal.deviceIntegrity.deviceRecognitionVerdict.0', 'UNEVALUATED');

            $meetsDevice = in_array($deviceVerdict, [
                'MEETS_DEVICE_INTEGRITY',
                'MEETS_STRONG_INTEGRITY',
                'MEETS_VIRTUAL_INTEGRITY',
            ], true);

            if ($meetsDevice && $appVerdict === 'PLAY_RECOGNIZED') {
                Log::info('play_integrity: pass', [
                    'user_id'        => $userId,
                    'endpoint'       => $endpoint,
                    'app_verdict'    => $appVerdict,
                    'device_verdict' => $deviceVerdict,
                ]);
            } else {
                // Below threshold — log warning but allow (v1 fail-open policy).
                Log::warning('play_integrity: low_verdict', [
                    'user_id'        => $userId,
                    'endpoint'       => $endpoint,
                    'app_verdict'    => $appVerdict,
                    'device_verdict' => $deviceVerdict,
                ]);
            }
        } catch (\Illuminate\Http\Client\ConnectionException) {
            Log::warning('play_integrity: integrity_api_timeout', [
                'user_id'  => $userId,
                'endpoint' => $endpoint,
            ]);
        } catch (\Throwable $e) {
            Log::error('play_integrity: unexpected_error', [
                'user_id'  => $userId,
                'endpoint' => $endpoint,
                'error'    => $e->getMessage(),
            ]);
        }

        return $next($request);
    }

    /**
     * Decode the base64 service-account JSON from env and exchange it for a
     * short-lived OAuth 2.0 access token scoped to the Play Integrity API.
     */
    private function getGoogleAccessToken(array $credentials): string
    {
        $now  = time();
        $exp  = $now + 3600;

        $header  = base64_encode(json_encode(['alg' => 'RS256', 'typ' => 'JWT']));
        $payload = base64_encode(json_encode([
            'iss'   => $credentials['client_email'],
            'scope' => 'https://www.googleapis.com/auth/playintegrity',
            'aud'   => 'https://oauth2.googleapis.com/token',
            'iat'   => $now,
            'exp'   => $exp,
        ]));

        $signingInput = "{$header}.{$payload}";

        $privateKey = openssl_pkey_get_private($credentials['private_key']);
        if (! $privateKey) {
            throw new \RuntimeException('play_integrity: failed to load private key');
        }

        openssl_sign($signingInput, $signature, $privateKey, OPENSSL_ALGO_SHA256);
        $signatureB64 = rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');

        $jwt = "{$signingInput}.{$signatureB64}";

        $tokenResponse = Http::timeout(5)->asForm()->post(
            'https://oauth2.googleapis.com/token',
            [
                'grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion'  => $jwt,
            ]
        );

        if (! $tokenResponse->successful()) {
            throw new \RuntimeException('play_integrity: failed to obtain access token');
        }

        return $tokenResponse->json('access_token');
    }

    /**
     * Load and decode the service account credentials from the GOOGLE_PLAY_INTEGRITY_CREDENTIALS_JSON
     * env var (expected to be base64-encoded service account JSON).
     */
    private function loadCredentials(): ?array
    {
        $raw = config('services.play_integrity.credentials_json');
        if (! $raw) {
            return null;
        }

        $decoded = base64_decode($raw, strict: true);
        if ($decoded === false) {
            return null;
        }

        $data = json_decode($decoded, true);
        return is_array($data) ? $data : null;
    }
}
