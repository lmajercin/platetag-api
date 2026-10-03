<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('session_share_tokens', function (Blueprint $table) {
            $table->id();
            $table->foreignId('session_id')
                  ->constrained('discovery_sessions')
                  ->cascadeOnDelete();
            $table->foreignId('created_by')
                  ->constrained('users')
                  ->cascadeOnDelete();
            $table->string('token', 64)->unique();
            $table->timestamp('expires_at');
            $table->timestamps();

            $table->index('token');
            $table->index('expires_at');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('session_share_tokens');
    }
};
