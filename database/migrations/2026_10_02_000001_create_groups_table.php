<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('groups', function (Blueprint $table) {
            $table->id();
            $table->string('name', 100);
            $table->foreignId('leader_id')->constrained('users')->onDelete('cascade');
            $table->boolean('is_public')->default(false);
            $table->integer('member_cap')->nullable()->default(25);
            $table->string('invite_token', 128)->nullable();
            $table->integer('invite_token_uses')->default(0);
            $table->integer('invite_max_uses')->nullable(); // NULL = unlimited (public groups)
            $table->timestamp('invite_expires_at')->nullable();
            $table->enum('game_mode', ['lifetime', 'fresh_start'])->default('lifetime');
            $table->timestamps();
            $table->softDeletes(); // deleted_at column for soft deletes
            
            $table->index('leader_id');
            $table->index('is_public');
            $table->index('invite_token');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('groups');
    }
};
