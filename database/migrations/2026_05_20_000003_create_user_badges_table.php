<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('user_badges', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            // RESTRICT: prevents accidental admin deletion of a badge from silently
            // wiping all users' earned records for it (Audit item #2).
            $table->foreignId('badge_id')->constrained()->restrictOnDelete();
            $table->timestamp('awarded_at');
            $table->unique(['user_id', 'badge_id']); // hard backstop against duplicate awards
            $table->index('user_id');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('user_badges');
    }
};
