<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use App\Models\User;
use App\Services\SocialTokenVerifier;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

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
            'provider' => ['required', 'string', 'in:google,facebook'],
            'token'    => ['required', 'string', 'max:4096'],
        ]);

        $providerUser = $this->verifier->verify($data['provider'], $data['token']);

        if (! $providerUser || empty($providerUser['id'])) {
            // Generic error — never reveal whether an account exists
            return response()->json(['message' => 'Sign-in failed. Please try again.'], 401);
        }

        $user = DB::transaction(function () use ($data, $providerUser) {
            // 1. Look up existing social account row (lock to prevent race conditions)
            $socialAccount = SocialAccount::where('provider', $data['provider'])
                ->where('provider_user_id', $providerUser['id'])
                ->lockForUpdate()
                ->first();

            if ($socialAccount) {
                // Update cached provider email in case it changed
                $socialAccount->update(['provider_email' => $providerUser['email']]);
                return $socialAccount->user;
            }

            // 2. Auto-link to existing PlateTag account if email is provider-verified
            $user = null;
            if (! empty($providerUser['email']) && $providerUser['email_verified']) {
                $user = User::where('email', $providerUser['email'])->first();
            }

            // 3. Create a new account if no match found
            if (! $user) {
                $name = trim($providerUser['name'] ?? '');
                if (! $name) {
                    // Edge case: provider returned no name (rare); reject gracefully
                    return null;
                }

                $providerEmail = $providerUser['email'] ?? null;
                $providerEmailVerified = ! empty($providerUser['email_verified']) && ! empty($providerEmail);

                $user = User::create([
                    'name'     => $name,
                    'email'    => $providerEmail,
                    // Random bcrypt hash — social-only account, this password can never be guessed or used
                    'password' => \Illuminate\Support\Facades\Hash::make(\Illuminate\Support\Str::random(32)),
                ]);

                // email_verified_at is intentionally excluded from $fillable — set via forceFill
                // to prevent mass-assignment bypass while still marking verified OAuth emails.
                if ($providerEmailVerified) {
                    $user->forceFill(['email_verified_at' => now()])->save();
                }

                // Auto-create the default General session every new user gets
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
