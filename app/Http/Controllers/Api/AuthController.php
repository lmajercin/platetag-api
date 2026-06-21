<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use App\Services\SocialTokenVerifier;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use App\Notifications\MobileEmailChange;
use App\Notifications\MobileEmailChangedNotice;
use App\Notifications\MobilePasswordReset;
use Illuminate\Support\Facades\Notification;
use Carbon\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

class AuthController extends Controller
{
    public function register(Request $request): JsonResponse
    {
        $data = $request->validate([
            'name'                  => ['required', 'string', 'max:255'],
            'email'                 => ['required', 'email', 'max:191', 'unique:users'],
            'password'              => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        $user = User::create([
            'name'     => $data['name'],
            'email'    => $data['email'],
            'password' => Hash::make($data['password']),
        ]);

        try {
            $user->sendEmailVerificationNotification();
        } catch (\Exception $e) {
            // Email delivery failed, but don't block registration
            \Log::warning("Email verification failed for user {$user->id}: {$e->getMessage()}");
        }

        // Grant founding member status if registering within the founding window.
        // Done at registration only — not repeated on every login.
        $cutoff = Carbon::parse(config('app.founding_member_cutoff'));
        if (now()->lte($cutoff)) {
            $user->forceFill([
                'is_founding_member' => true,
                'is_premium'         => true,
                'premium_granted_at' => now(),
            ])->save();
        }

        // Auto-create the permanent "General" session for every new user
        DB::table('discovery_sessions')->insert([
            'user_id'    => $user->id,
            'name'       => 'General',
            'is_default' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $token = $user->createToken('mobile')->plainTextToken;

        return response()->json([
            'token' => $token,
            'user'  => [
                'id'    => $user->id,
                'name'  => $user->name,
                'email' => $user->email,
            ],
        ], 201);
    }

    public function login(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email'    => ['required', 'email'],
            'password' => ['required', 'string'],
        ]);

        // Per-email lockout: max 5 failed attempts per 5-minute window.
        // This is independent of the IP-based throttle:auth middleware.
        $emailKey = 'login_fail:' . Str::lower($data['email']);
        if (RateLimiter::tooManyAttempts($emailKey, 5)) {
            $seconds = RateLimiter::availableIn($emailKey);
            return response()->json([
                'message' => 'Too many login attempts for this account. Try again in ' . $seconds . ' seconds.',
            ], 429);
        }

        $user = User::where('email', $data['email'])->first();

        if (! $user || ! Hash::check($data['password'], $user->password)) {
            RateLimiter::hit($emailKey, 300); // 5-minute decay
            throw ValidationException::withMessages([
                'email' => ['The provided credentials are incorrect.'],
            ]);
        }

        RateLimiter::clear($emailKey); // Reset on successful login

        // Revoke all old mobile tokens on login (single-device policy for v1)
        $user->tokens()->where('name', 'mobile')->delete();
        $token = $user->createToken('mobile')->plainTextToken;

        return response()->json([
            'token' => $token,
            'user'  => [
                'id'    => $user->id,
                'name'  => $user->name,
                'email' => $user->email,
            ],
        ]);
    }

    public function logout(Request $request): JsonResponse
    {
        $request->user()->currentAccessToken()->delete();
        return response()->json(['message' => 'Logged out.']);
    }

    /**
     * POST /api/v1/auth/web/login
     *
     * Web SPA login — establishes a Sanctum cookie session.
     * Returns the authenticated user (no token). Mobile login is unchanged.
     */
    public function webLogin(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email'    => ['required', 'email'],
            'password' => ['required', 'string'],
        ]);

        $emailKey = 'login_fail:' . Str::lower($data['email']);
        if (RateLimiter::tooManyAttempts($emailKey, 5)) {
            $seconds = RateLimiter::availableIn($emailKey);
            return response()->json([
                'message' => 'Too many login attempts for this account. Try again in ' . $seconds . ' seconds.',
            ], 429);
        }

        if (! \Illuminate\Support\Facades\Auth::attempt(['email' => $data['email'], 'password' => $data['password']])) {
            RateLimiter::hit($emailKey, 300);
            throw ValidationException::withMessages([
                'email' => ['The provided credentials are incorrect.'],
            ]);
        }

        RateLimiter::clear($emailKey);
        $request->session()->regenerate();

        $user = $request->user();
        return response()->json(['user' => [
            'id'    => $user->id,
            'name'  => $user->name,
            'email' => $user->email,
        ]]);
    }

    /**
     * POST /api/v1/auth/web/register
     *
     * Web SPA registration — creates account and establishes a cookie session.
     * Returns the new user (no token). Mobile register is unchanged.
     */
    public function webRegister(Request $request): JsonResponse
    {
        $data = $request->validate([
            'name'                  => ['required', 'string', 'max:255'],
            'email'                 => ['required', 'email', 'max:191', 'unique:users'],
            'password'              => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        $user = User::create([
            'name'     => $data['name'],
            'email'    => $data['email'],
            'password' => Hash::make($data['password']),
        ]);

        $user->sendEmailVerificationNotification();

        $cutoff = Carbon::parse(config('app.founding_member_cutoff'));
        if (now()->lte($cutoff)) {
            $user->forceFill([
                'is_founding_member' => true,
                'is_premium'         => true,
                'premium_granted_at' => now(),
            ])->save();
        }

        DB::table('discovery_sessions')->insert([
            'user_id'    => $user->id,
            'name'       => 'General',
            'is_default' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        \Illuminate\Support\Facades\Auth::login($user);
        $request->session()->regenerate();

        return response()->json(['user' => [
            'id'    => $user->id,
            'name'  => $user->name,
            'email' => $user->email,
        ]], 201);
    }

    /**
     * POST /api/v1/auth/web/logout
     *
     * Web SPA logout — invalidates the cookie session.
     */
    public function webLogout(Request $request): JsonResponse
    {
        \Illuminate\Support\Facades\Auth::logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();
        return response()->json(['message' => 'Logged out.']);
    }

    public function me(Request $request): JsonResponse
    {
        $user = $request->user();
        $socialAccount = $user->socialAccounts()->first();
        return response()->json([
            'id'                 => $user->id,
            'name'               => $user->name,
            'email'              => $user->email,
            'email_verified'     => $user->hasVerifiedEmail(),
            'auth_provider'      => $socialAccount ? $socialAccount->provider : 'email',
            'is_premium'         => (bool) $user->is_premium,
            'is_founding_member' => (bool) $user->is_founding_member,
            'promo_expires_at'   => $user->promo_expires_at?->toISOString(),
        ]);
    }

    public function updateMe(Request $request): JsonResponse
    {
        $data = $request->validate([
            'name' => ['required', 'string', 'max:255'],
        ]);

        $request->user()->forceFill(['name' => $data['name']])->save();

        $user = $request->user()->fresh();
        $socialAccount = $user->socialAccounts()->first();
        return response()->json([
            'id'                 => $user->id,
            'name'               => $user->name,
            'email'              => $user->email,
            'email_verified'     => $user->hasVerifiedEmail(),
            'auth_provider'      => $socialAccount ? $socialAccount->provider : 'email',
            'is_premium'         => (bool) $user->is_premium,
            'is_founding_member' => (bool) $user->is_founding_member,
            'promo_expires_at'   => $user->promo_expires_at?->toISOString(),
        ]);
    }

    public function forgotPassword(Request $request): JsonResponse
    {
        $request->validate(['email' => ['required', 'email']]);

        $emailKey = Str::lower(trim((string) $request->email));
        $requestKey = 'pwd_reset_request:' . $emailKey;

        // Cooldown for reset code requests per account identifier.
        // Always return a generic success message to avoid user enumeration.
        if (RateLimiter::tooManyAttempts($requestKey, 1)) {
            return response()->json([
                'message' => 'If that email is registered, a reset code has been sent.',
            ]);
        }

        RateLimiter::hit($requestKey, 60);

        // Always return success to prevent user enumeration
        $user = User::where('email', $request->email)->first();
        if ($user) {
            // Generate a 6-digit OTP, store hashed, expire in 30 minutes
            $otp = (string) random_int(100000, 999999);

            DB::table('mobile_otp_resets')
                ->where('email', $user->email)
                ->delete();

            DB::table('mobile_otp_resets')->insert([
                'email'      => $user->email,
                'otp_hash'   => Hash::make($otp),
                'attempts'   => 0,
                'expires_at' => now()->addMinutes(30),
                'created_at' => now(),
            ]);

            $user->notify(new MobilePasswordReset($otp));
        }

        return response()->json([
            'message' => 'If that email is registered, a reset code has been sent.',
        ]);
    }

    public function resetPassword(Request $request): JsonResponse
    {
        $data = $request->validate([
            'email'    => ['required', 'email'],
            'token'    => ['required', 'string'],
            'password' => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        $emailKey = Str::lower(trim($data['email']));
        $attemptKey = 'pwd_reset_verify:' . $emailKey;

        // Account-level brute force protection for OTP verification.
        if (RateLimiter::tooManyAttempts($attemptKey, 10)) {
            return response()->json([
                'message' => 'Too many reset attempts. Please request a new reset code and try again later.',
            ], 429);
        }

        $result = DB::transaction(function () use ($data, $attemptKey) {
            $record = DB::table('mobile_otp_resets')
                ->where('email', $data['email'])
                ->lockForUpdate()
                ->first();

            if (! $record) {
                RateLimiter::hit($attemptKey, 900); // 15-minute decay window

                return [
                    'status'  => 422,
                    'message' => 'Invalid or expired reset code. Please request a new one.',
                ];
            }

            if (now()->isAfter($record->expires_at)) {
                DB::table('mobile_otp_resets')->where('email', $data['email'])->delete();
                RateLimiter::hit($attemptKey, 900);

                return [
                    'status'  => 422,
                    'message' => 'Invalid or expired reset code. Please request a new one.',
                ];
            }

            $attempts = (int) ($record->attempts ?? 0);
            if ($attempts >= 5) {
                DB::table('mobile_otp_resets')->where('email', $data['email'])->delete();
                RateLimiter::hit($attemptKey, 900);

                return [
                    'status'  => 429,
                    'message' => 'Too many reset attempts. Please request a new reset code and try again later.',
                ];
            }

            if (! Hash::check($data['token'], $record->otp_hash)) {
                $attempts += 1;

                if ($attempts >= 5) {
                    DB::table('mobile_otp_resets')->where('email', $data['email'])->delete();
                    RateLimiter::hit($attemptKey, 900);

                    return [
                        'status'  => 429,
                        'message' => 'Too many reset attempts. Please request a new reset code and try again later.',
                    ];
                }

                DB::table('mobile_otp_resets')
                    ->where('email', $data['email'])
                    ->update(['attempts' => $attempts]);

                RateLimiter::hit($attemptKey, 900);

                return [
                    'status'  => 422,
                    'message' => 'Invalid or expired reset code. Please request a new one.',
                ];
            }

            $user = User::where('email', $data['email'])->lockForUpdate()->first();
            if (! $user) {
                RateLimiter::hit($attemptKey, 900);

                return [
                    'status'  => 422,
                    'message' => 'Invalid or expired reset code. Please request a new one.',
                ];
            }

            $user->forceFill(['password' => Hash::make($data['password'])])->save();
            $user->tokens()->delete();

            // Consume the OTP after successful password change.
            DB::table('mobile_otp_resets')->where('email', $data['email'])->delete();
            RateLimiter::clear($attemptKey);

            return [
                'status'  => 200,
                'message' => 'Password reset successfully. Please log in.',
            ];
        });

        return response()->json(['message' => $result['message']], $result['status']);
    }

    public function resendVerification(Request $request): JsonResponse
    {
        $user = $request->user();

        if ($user->hasVerifiedEmail()) {
            return response()->json(['message' => 'Email already verified.']);
        }

        $user->sendEmailVerificationNotification();

        return response()->json(['message' => 'Verification email sent.']);
    }

    public function changePassword(Request $request): JsonResponse
    {
        if ($request->user()->socialAccounts()->exists()) {
            return response()->json(['message' => 'Password management is not available for accounts created with a social provider.'], 403);
        }

        $data = $request->validate([
            'current_password' => ['required', 'string'],
            'password'         => ['required', 'string', 'min:8', 'confirmed'],
        ]);

        if (! Hash::check($data['current_password'], $request->user()->password)) {
            throw ValidationException::withMessages([
                'current_password' => ['Current password is incorrect.'],
            ]);
        }

        $request->user()->forceFill(['password' => Hash::make($data['password'])])->save();

        // Revoke all other tokens — user must log in again on other devices
        $currentId = $request->user()->currentAccessToken()->id;
        $request->user()->tokens()->where('id', '!=', $currentId)->delete();

        return response()->json(['message' => 'Password updated successfully.']);
    }

    public function deleteAccount(Request $request): JsonResponse
    {
        $user = $request->user();

        if ($user->socialAccounts()->exists()) {
            // Social-only account — registered via OAuth; require provider re-authentication
            $data = $request->validate([
                'provider' => ['required', 'string', 'in:google,facebook'],
                'token'    => ['required', 'string', 'max:4096'],
            ]);

            $verifier     = app(SocialTokenVerifier::class);
            $providerUser = $verifier->verify($data['provider'], $data['token']);

            if (! $providerUser) {
                return response()->json(['message' => 'Re-authentication failed.'], 401);
            }

            $linked = $user->socialAccounts()
                ->where('provider', $data['provider'])
                ->where('provider_user_id', $providerUser['id'])
                ->exists();

            if (! $linked) {
                return response()->json(['message' => 'Re-authentication failed.'], 401);
            }
        } else {
            $data = $request->validate([
                'password' => ['required', 'string'],
            ]);

            if (! Hash::check($data['password'], $user->password)) {
                throw ValidationException::withMessages([
                    'password' => ['Password is incorrect.'],
                ]);
            }
        }

        DB::transaction(function () use ($user) {
            DB::table('user_discovered_plates')->where('user_id', $user->id)->delete();
            DB::table('social_accounts')->where('user_id', $user->id)->delete();
            $user->tokens()->delete();
            $user->delete();
        });

        return response()->json(['message' => 'Account deleted.']);
    }

    public function requestEmailChange(Request $request): JsonResponse
    {
        if ($request->user()->socialAccounts()->exists()) {
            return response()->json(['message' => 'Email management is not available for accounts created with a social provider.'], 403);
        }

        $data = $request->validate([
            'email'    => ['required', 'email', 'max:191', 'unique:users,email'],
            'password' => ['required', 'string'],
        ]);

        if (! Hash::check($data['password'], $request->user()->password)) {
            throw ValidationException::withMessages([
                'password' => ['Current password is incorrect.'],
            ]);
        }

        $otp = (string) random_int(100000, 999999);

        DB::table('mobile_email_changes')
            ->where('user_id', $request->user()->id)
            ->delete();

        DB::table('mobile_email_changes')->insert([
            'user_id'    => $request->user()->id,
            'new_email'  => $data['email'],
            'otp_hash'   => Hash::make($otp),
            'expires_at' => now()->addMinutes(30),
            'created_at' => now(),
        ]);

        // Send OTP to the NEW email address (anonymous route so it goes to new address, not current)
        Notification::route('mail', $data['email'])
            ->notify(new MobileEmailChange($otp));

        return response()->json(['message' => 'Verification code sent to your new email address.']);
    }

    public function confirmEmailChange(Request $request): JsonResponse
    {
        $data = $request->validate([
            'otp' => ['required', 'string'],
        ]);

        $record = DB::table('mobile_email_changes')
            ->where('user_id', $request->user()->id)
            ->first();

        if (! $record || now()->isAfter($record->expires_at)) {
            DB::table('mobile_email_changes')->where('user_id', $request->user()->id)->delete();
            return response()->json(['message' => 'Invalid or expired code. Please start over.'], 422);
        }

        // OTP exhaustion: lock out after 5 failed attempts
        if (! Hash::check($data['otp'], $record->otp_hash)) {
            $attempts = ($record->attempts ?? 0) + 1;
            if ($attempts >= 5) {
                DB::table('mobile_email_changes')->where('user_id', $request->user()->id)->delete();
                return response()->json(['message' => 'Too many failed attempts. Please start over.'], 422);
            }
            DB::table('mobile_email_changes')
                ->where('user_id', $request->user()->id)
                ->update(['attempts' => $attempts]);
            return response()->json(['message' => 'Invalid or expired code. Please start over.'], 422);
        }

        // Re-check uniqueness — address could have been registered between request and confirm
        $emailTaken = User::where('email', $record->new_email)
            ->where('id', '!=', $request->user()->id)
            ->exists();

        if ($emailTaken) {
            DB::table('mobile_email_changes')->where('user_id', $request->user()->id)->delete();
            return response()->json(['message' => 'That email address is no longer available.'], 422);
        }

        $oldEmail = $request->user()->email;

        $request->user()->forceFill([
            'email'             => $record->new_email,
            'email_verified_at' => now(), // confirmed via OTP delivered to the new address
        ])->save();

        DB::table('mobile_email_changes')->where('user_id', $request->user()->id)->delete();

        // Notify the old address so the account owner knows about the change
        Notification::route('mail', $oldEmail)
            ->notify(new MobileEmailChangedNotice($record->new_email));

        $user = $request->user()->fresh();
        return response()->json([
            'message' => 'Email updated successfully.',
            'user'    => [
                'id'             => $user->id,
                'name'           => $user->name,
                'email'          => $user->email,
                'email_verified' => true,
            ],
        ]);
    }
}
