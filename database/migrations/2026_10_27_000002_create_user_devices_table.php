<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

// @Audit GO: 2026-10-27 — Build 91 (5a). Push notification token storage.
// Composite unique on (user_id, platform): one active token per platform per user.
// Unique on push_token: cross-user integrity (duplicate token impossible in practice — defensive).
// updateOrCreate(['user_id', 'platform']) handles token refresh on reinstall without duplication.

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('user_devices', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->string('push_token', 255);
            $table->enum('platform', ['ios', 'android']);
            $table->timestamps();

            $table->unique(['user_id', 'platform']); // one token per platform per user
            $table->unique('push_token');             // cross-user integrity guard
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('user_devices');
    }
};
