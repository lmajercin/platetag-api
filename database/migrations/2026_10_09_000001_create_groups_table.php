<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

// @Audit GO: 2026-10-01 — Build 87a scope reviewed and approved.
// Rebuild from wiped state — same schema, no changes.

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('groups', function (Blueprint $table) {
            $table->id();
            $table->string('name', 255);
            $table->text('description')->nullable();
            $table->foreignId('leader_id')->constrained('users')->cascadeOnDelete();
            $table->boolean('is_private')->default(false);

            // Invite tokens — private (single-use) and public (unlimited)
            $table->string('invite_token_private', 64)->nullable()->unique();
            $table->string('invite_token_public', 64)->nullable()->unique();
            $table->unsignedInteger('private_token_uses')->default(0);
            $table->unsignedInteger('public_token_uses')->default(0);
            $table->timestamp('private_token_expires_at')->nullable();
            $table->timestamp('public_token_expires_at')->nullable();

            $table->unsignedInteger('member_cap')->nullable();
            $table->char('country', 2)->default('US'); // 'US' or 'CA' — for 50 States Game

            $table->timestamps();
            $table->softDeletes();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('groups');
    }
};
