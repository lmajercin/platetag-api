<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use App\Models\User;
use App\Services\SocialTokenVerifier;
use Firebase\JWT\JWT;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class SocialAuthController extends Controller
{
    public function __construct(private SocialTokenVerifier $verifier) {}

    /**
     * POST /api/v1/auth/social/callback
     *
     * Accepts a social provider name and its access token. Verifies the token
     * server-side, then finds, links, or creates the PlateTag user account.
     * Returns a Sanctum token on success.
     */
    public function callback(Request $request): JsonResponse
    {
        $data = $request->validate([
            'provider'           => ['required', 'string', 'in:google,facebook,apple'],
            'token'              => ['required', 'string', 'max:4096'],
            // Apple-only fields — ignored for google/facebook
            'authorization_code' => ['nullable', 'string', 'max:1024'],
            'name'               => ['nullable', 'string', 'max:255'],
        ]);

        $providerUser = $this->verifier->verify($data['provider'], $data['token']);

        if (! $providerUser || empty($providerUser['id'])) {
            // Generic error — never reveal whether an account exists
            return response()->json(['message' => 'Sign-in failed. Please try again.'], 401);
        }

        // For Apple: exchange the authorization_code for a refresh_token now,
        // before the transaction, so we don't hold a DB lock during an HTTP call.
        $appleRefreshToken = null;
        if ($data['provider'] === 'apple' && ! empty($data['authorization_code'])) {
            $appleRefreshToken = $this->exchangeAppleAuthCode($data['authorization_code']);
            // Log but don't fail — revocation is best-effort; sign-in must succeed
            if (! $appleRefreshToken) {
                Log::warning('Apple authorization_code exchange failed — refresh_token not stored', [
                    'sub' => $providerUser['id'],
                ]);
            }
        }

        $user = DB::transaction(function () use ($data, $providerUser, $appleRefreshToken) {
            // 1. Look up existing social account row (lock to prevent race conditions)
            $socialAccount = SocialAccount::where('provider', $data['provider'])
                ->where('provider_user_id', $providerUser['id'])
                ->lockForUpdate()
                ->first();

            if ($socialAccount) {
                // Update cached email and refresh token on repeat sign-ins
                $updates = ['provider_email' => $providerUser['email'] ?? $socialAccount->provider_email];
                if ($appleRefreshToken) {
                    $updates['apple_refresh_token'] = $appleRefreshToken;
                }
                $socialAccount->update($updates);
                return $socialAccount->user;
            }

            // 2. Auto-link to existing PlateTag account if email is provider-verified
            $user = null;
            if (! empty($providerUser['email']) && $providerUser['email_verified']) {
                $user = User::where('email', $providerUser['email'])->first();
            }

            // 3. Create a new account if no match found
            if (! $user) {
                // Apple: name comes from request body (SDK response). Google/Facebook: from token.
                $name = trim($data['name'] ?? $providerUser['name'] ?? '');
                if (! $name) {
                    // Apple sends name only on first sign-in. If missing, use email prefix as fallback.
                    $email = $providerUser['email'] ?? null;
                    $name  = $email ? explode('@', $email)[0] : '';
                }
                if (! $name) {
                    return null;
                }

                $providerEmail         = $providerUser['email'] ?? null;
                $providerEmailVerified = ! empty($providerUser['email_verified']) && ! empty($providerEmail);

                $user = User::create([
                    'name'     => $name,
                    'email'    => $providerEmail,
                    // Random bcrypt hash — social-only account, this password can never be used
                    'password' => \Illuminate\Support\Facades\Hash::make(\Illuminate\Support\Str::random(32)),
                ]);

                // email_verified_at is intentionally excluded from $fillable — set via forceFill
                if ($providerEmailVerified) {
                    $user->forceFill(['email_verified_at' => now()])->save();
                }

                DB::table('discovery_sessions')->insert([
                    'user_id'    => $user->id,
                    'name'       => 'General',
                    'is_default' => true,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            // 4. Create the social_accounts link
            SocialAccount::create([
                'user_id'             => $user->id,
                'provider'            => $data['provider'],
                'provider_user_id'    => $providerUser['id'],
                'provider_email'      => $providerUser['email'] ?? null,
                'apple_refresh_token' => $appleRefreshToken,
            ]);

            return $user;
        });

        if (! $user) {
            return response()->json(['message' => 'Sign-in failed. Please try again.'], 422);
        }

        // Revoke old mobile tokens and issue a fresh one
        $user->tokens()->where('name', 'mobile')->delete();
        $sanctumToken = $user->createToken('mobile')->plainTextToken;

        return response()->json([
            'token' => $sanctumToken,
            'user'  => [
                'id'    => $user->id,
                'name'  => $user->name,
                'email' => $user->email,
            ],
        ]);
    }

    /**
     * Exchange an Apple authorization_code for a refresh_token.
     * Public so AuthController can call it during account deletion.
     * The refresh_token is stored encrypted in social_accounts and used
     * only when revoking access on account deletion (App Store requirement).
     */
    public function exchangeAppleAuthCode(string $authorizationCode): ?string
    {
        try {
            $clientSecret = $this->buildAppleClientSecret();

            $response = Http::timeout(15)->asForm()->post('https://appleid.apple.com/auth/token', [
                'client_id'     => config('services.apple.bundle_id'),
                'client_secret' => $clientSecret,
                'code'          => $authorizationCode,
                'grant_type'    => 'authorization_code',
            ]);

            if (! $response->successful()) {
                Log::error('Apple token exchange failed', ['body' => $response->body()]);
                return null;
            }

            return $response->json('refresh_token');
        } catch (\Exception $e) {
            Log::error('Apple token exchange exception', ['error' => $e->getMessage()]);
            return null;
        }
    }

    /**
     * Revoke an Apple refresh_token via Apple's revocation endpoint.
     * Called during account deletion to satisfy App Store Guideline 5.1.1(v).
     */
    public function revokeAppleToken(string $refreshToken): void
    {
        try {
            $clientSecret = $this->buildAppleClientSecret();

            $response = Http::timeout(15)->asForm()->post('https://appleid.apple.com/auth/revoke', [
                'client_id'       => config('services.apple.bundle_id'),
                'client_secret'   => $clientSecret,
                'token'           => $refreshToken,
                'token_type_hint' => 'refresh_token',
            ]);

            if (! $response->successful()) {
                Log::warning('Apple token revocation failed — proceeding with account deletion', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
            }
        } catch (\Exception $e) {
            // Log but do not throw — account deletion must not be blocked by a revocation failure
            Log::warning('Apple token revocation exception — proceeding with account deletion', [
                'error' => $e->getMessage(),
            ]);
        }
    }

    /**
     * Build a signed Apple client_secret JWT.
     * Required for both authorization_code exchange and token revocation.
     * Valid for 3 minutes — Apple max is 6 months but short-lived is safer.
     */
    private function buildAppleClientSecret(): string
    {
        $teamId   = config('services.apple.team_id');
        $keyId    = config('services.apple.key_id');
        $bundleId = config('services.apple.bundle_id');
        $keyPath  = config('services.apple.private_key_path');

        if (! file_exists($keyPath)) {
            throw new \RuntimeException("Apple .p8 private key not found at: {$keyPath}");
        }

        $privateKey = file_get_contents($keyPath);
        $now        = time();

        $payload = [
            'iss' => $teamId,
            'iat' => $now,
            'exp' => $now + 180, // 3 minutes
            'aud' => 'https://appleid.apple.com',
            'sub' => $bundleId,
        ];

        return JWT::encode($payload, $privateKey, 'ES256', $keyId);
    }

    /**
     * POST /api/v1/auth/social/web-callback
     *
     * Web-only social sign-in. Same provider token verification as the mobile
     * callback, but establishes a Sanctum cookie session instead of issuing a
     * bearer token. Mobile tokens are never touched here — web and mobile
     * sessions are completely independent.
     */
    public function webCallback(Request $request): JsonResponse
    {
        $data = $request->validate([
            'provider' => ['required', 'string', 'in:google,facebook'],
            'token'    => ['required', 'string', 'max:4096'],
        ]);

        $providerUser = $this->verifier->verify($data['provider'], $data['token']);

        if (! $providerUser || empty($providerUser['id'])) {
            return response()->json(['message' => 'Sign-in failed. Please try again.'], 401);
        }

        $user = DB::transaction(function () use ($data, $providerUser) {
            $socialAccount = SocialAccount::where('provider', $data['provider'])
                ->where('provider_user_id', $providerUser['id'])
                ->lockForUpdate()
                ->first();

            if ($socialAccount) {
                $socialAccount->update(['provider_email' => $providerUser['email']]);
                return $socialAccount->user;
            }

            $user = null;
            if (! empty($providerUser['email']) && $providerUser['email_verified']) {
                $user = User::where('email', $providerUser['email'])->first();
            }

            if (! $user) {
                $name = trim($providerUser['name'] ?? '');
                if (! $name) {
                    return null;
                }

                $providerEmail = $providerUser['email'] ?? null;
                $providerEmailVerified = ! empty($providerUser['email_verified']) && ! empty($providerEmail);

                $user = User::create([
                    'name'     => $name,
                    'email'    => $providerEmail,
                    'password' => \Illuminate\Support\Facades\Hash::make(\Illuminate\Support\Str::random(32)),
                ]);

                // email_verified_at is intentionally excluded from $fillable — set via forceFill
                if ($providerEmailVerified) {
                    $user->forceFill(['email_verified_at' => now()])->save();
                }

                DB::table('discovery_sessions')->insert([
                    'user_id'    => $user->id,
                    'name'       => 'General',
                    'is_default' => true,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            SocialAccount::create([
                'user_id'          => $user->id,
                'provider'         => $data['provider'],
                'provider_user_id' => $providerUser['id'],
                'provider_email'   => $providerUser['email'],
            ]);

            return $user;
        });

        if (! $user) {
            return response()->json(['message' => 'Sign-in failed. Please try again.'], 422);
        }

        // Establish a Sanctum cookie session for the web SPA.
        // No bearer token is issued — the browser receives a session cookie.
        // Mobile tokens (named 'mobile') are never touched here.
        \Illuminate\Support\Facades\Auth::login($user);
        $request->session()->regenerate();

        return response()->json([
            'user' => [
                'id'    => $user->id,
                'name'  => $user->name,
                'email' => $user->email,
            ],
        ]);
    }
}
