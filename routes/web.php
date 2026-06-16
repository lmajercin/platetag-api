<?php

use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('welcome');
});

// Email verification endpoint — user clicks link from email, opens in phone browser.
// Uses Laravel's signed URL validation (no session needed).
Route::get('/email/verify/{id}/{hash}', function (Request $request, string $id, string $hash) {
    // Reject if signature is invalid or expired
    if (! $request->hasValidSignature()) {
        return response('<html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#dc2626">&#10007; Invalid or Expired Link</h2>
            <p style="color:#555">This verification link is invalid or has expired.<br>
            Please request a new one from the PlateTag app.</p>
        </body></html>', 403)->header('Content-Type', 'text/html');
    }

    $user = User::find((int) $id);

    if (! $user || ! hash_equals(sha1($user->getEmailForVerification()), $hash)) {
        return response('<html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#dc2626">&#10007; Verification Failed</h2>
            <p style="color:#555">We could not verify this email address.</p>
        </body></html>', 403)->header('Content-Type', 'text/html');
    }

    if ($user->hasVerifiedEmail()) {
        return response('<html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#2563eb">Already Verified</h2>
            <p style="color:#555">Your email is already verified. You can close this window.</p>
        </body></html>')->header('Content-Type', 'text/html');
    }

    $user->markEmailAsVerified();

    return response('<html><body style="font-family:sans-serif;text-align:center;padding:60px">
        <h2 style="color:#16a34a">&#10003; Email Verified</h2>
        <p style="color:#555">Your PlateTag email has been verified.<br>
        You can close this window and return to the app.</p>
    </body></html>')->header('Content-Type', 'text/html');
})->middleware('signed')->name('verification.verify');

