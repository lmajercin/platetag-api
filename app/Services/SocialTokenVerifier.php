<?php

namespace App\Services;

use Firebase\JWT\JWT;
use Firebase\JWT\JWK;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class SocialTokenVerifier
{
    /**
     * Verify a social provider token server-side.
     *
     * Returns an array with keys: id, email, email_verified, name
     * Returns null if verification fails for any reason.
     */
    public function verify(string $provider, string $token): ?array
    {
        try {
            return match ($provider) {
                'google'   => $this->verifyGoogle($token),
                'facebook' => $this->verifyFacebook($token),
                'apple'    => $this->verifyApple($token),
                default    => null,
            };
        } catch (\Exception $e) {
            Log::error('Social token verification failed', [
                'provider' => $provider,
                'error'    => $e->getMessage(),
            ]);
            return null;
        }
    }

    /**
     * Verify a Google token.
     *
     * Only ID tokens (JWT, starting with "eyJ") are accepted.
     * All builds since v1.2.0 / Build 31 use expo-auth-session which always
     * returns an ID token. Access token support has been retired.
     */
    private function verifyGoogle(string $token): ?array
    {
        if (! str_starts_with($token, 'eyJ')) {
            return null;
        }

        return $this->verifyGoogleIdToken($token);
    }

    /**
     * Verify a Google ID token (JWT) via Google's tokeninfo endpoint.
     */
    private function verifyGoogleIdToken(string $idToken): ?array
    {
        $response = Http::timeout(10)
            ->get('https://oauth2.googleapis.com/tokeninfo', ['id_token' => $idToken]);

        if (! $response->successful()) {
            return null;
        }

        $data = $response->json();

        if (empty($data['sub'])) {
            return null;
        }

        // Validate audience — the token must have been issued for a PlateTag OAuth client.
        // Without this check, a valid JWT from any Google application passes verification.
        $allowedAudiences = array_filter([
            config('services.google.client_id'),
            config('services.google.ios_client_id'),
            config('services.google.android_client_id'),
        ]);

        if (empty($data['aud']) || ! in_array($data['aud'], $allowedAudiences, true)) {
            Log::error('Google ID token audience mismatch', ['aud' => $data['aud'] ?? 'missing']);
            return null;
        }

        return [
            'id'             => $data['sub'],
            'email'          => $data['email'] ?? null,
            'email_verified' => filter_var($data['email_verified'] ?? false, FILTER_VALIDATE_BOOLEAN),
            'name'           => $data['name'] ?? null,
        ];
    }

    /**
     * Verify a Facebook access token via the debug_token endpoint,
     * then fetch the user profile.
     */
    private function verifyFacebook(string $accessToken): ?array
    {
        $appId     = config('services.facebook.client_id');
        $appSecret = config('services.facebook.client_secret');

        // Step 1: get app access token
        $appTokenResponse = Http::timeout(10)->get('https://graph.facebook.com/oauth/access_token', [
            'client_id'     => $appId,
            'client_secret' => $appSecret,
            'grant_type'    => 'client_credentials',
        ]);

        if (! $appTokenResponse->successful()) {
            return null;
        }

        $appToken = $appTokenResponse->json('access_token');

        // Step 2: debug / verify the user's token
        $debugResponse = Http::timeout(10)->get('https://graph.facebook.com/debug_token', [
            'input_token'  => $accessToken,
            'access_token' => $appToken,
        ]);

        if (! $debugResponse->successful()) {
            return null;
        }

        $debugData = $debugResponse->json('data');

        if (! ($debugData['is_valid'] ?? false)) {
            return null;
        }

        // Verify the token belongs to our Facebook app
        if (($debugData['app_id'] ?? '') !== (string) $appId) {
            return null;
        }

        // Step 3: fetch user profile
        $userResponse = Http::timeout(10)->get('https://graph.facebook.com/me', [
            'fields'       => 'id,name,email',
            'access_token' => $accessToken,
        ]);

        if (! $userResponse->successful()) {
            return null;
        }

        $userData = $userResponse->json();

        if (empty($userData['id'])) {
            return null;
        }

        return [
            'id'             => $userData['id'],
            'email'          => $userData['email'] ?? null,
            // Facebook only returns email when the user has granted permission and
            // the account email is verified — treat its presence as verified.
            'email_verified' => isset($userData['email']),
            'name'           => $userData['name'] ?? null,
        ];
    }

    /**
     * Verify an Apple identity token (JWT).
     *
     * Validates: RS256 signature via Apple JWKS, iss, aud (bundle ID), exp, sub.
     * Apple JWKS are cached for 1 hour so a momentary Apple outage does not
     * block sign-ins. Cache is keyed separately from other HTTP calls.
     *
     * Returns: id (Apple sub), email (may be null on repeat sign-ins), email_verified, name (always null — passed separately by app).
     */
    private function verifyApple(string $identityToken): ?array
    {
        $bundleId = config('services.apple.bundle_id');

        // Fetch Apple's public keys with 1-hour cache.
        $jwks = Cache::remember('apple_jwks', 3600, function () {
            $response = Http::timeout(10)->get('https://appleid.apple.com/auth/keys');
            if (! $response->successful()) {
                throw new \RuntimeException('Failed to fetch Apple JWKS');
            }
            return $response->json();
        });

        // Decode and verify the JWT using firebase/php-jwt
        $keys    = JWK::parseKeySet($jwks);
        $decoded = JWT::decode($identityToken, $keys);

        // Validate required claims explicitly
        if (($decoded->iss ?? '') !== 'https://appleid.apple.com') {
            Log::error('Apple token iss mismatch', ['iss' => $decoded->iss ?? 'missing']);
            return null;
        }

        if (($decoded->aud ?? '') !== $bundleId) {
            Log::error('Apple token aud mismatch', ['aud' => $decoded->aud ?? 'missing', 'expected' => $bundleId]);
            return null;
        }

        if (empty($decoded->sub)) {
            Log::error('Apple token missing sub claim');
            return null;
        }

        // exp is validated automatically by JWT::decode — throws ExpiredException if past
        return [
            'id'             => $decoded->sub,
            // Apple only sends email on first sign-in; subsequent logins return null.
            // The caller (SocialAuthController) uses the stored value for repeat sign-ins.
            'email'          => $decoded->email ?? null,
            'email_verified' => true, // Apple pre-verifies all emails
            'name'           => null, // name comes from app SDK response, not the JWT
        ];
    }
}
