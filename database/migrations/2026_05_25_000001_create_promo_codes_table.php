<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('promo_codes', function (Blueprint $table) {
            $table->id();

            // The code users enter. Always stored and compared uppercase.
            // Minimum 8 characters enforced at the application layer (Filament + FormRequest).
            $table->string('code', 32)->unique();

            // 'free' = permanent full access grant. 'founding_member' removed by design —
            // founding member status (is_founding_member) is only set at registration within
            // the founding window. A promo code must never be able to set is_founding_member.
            $table->enum('discount_type', ['free']);

            // Windowed access: starts_at/expires_at define when the code is valid.
            // expires_at null = no expiry (permanent code window).
            // Note: this is the code's own validity window, not the per-user access duration.
            // For windowed user access (e.g. 14-day trial), expires_at on this row drives
            // promo_expires_at on the redemption record.
            $table->timestamp('starts_at');
            $table->timestamp('expires_at')->nullable();

            // max_uses null = unlimited redemptions.
            $table->unsignedInteger('max_uses')->nullable();
            $table->unsignedInteger('uses_count')->default(0);

            // Admin kill switch — can disable a code without deleting it.
            $table->boolean('is_active')->default(true);

            // Internal note — never exposed to users.
            $table->text('notes')->nullable();

            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('promo_codes');
    }
};
