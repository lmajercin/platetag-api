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
        Schema::create('games', function (Blueprint $table) {
            $table->id();
            $table->foreignId('group_id')->constrained('groups')->onDelete('cascade');
            $table->enum('game_type', ['50_states'])->comment('road_rally added in Build 87b');
            $table->integer('target_count'); // 50 for US, 13 for Canada
            $table->string('country', 2); // 'US', 'CA'
            $table->date('start_date')->nullable();
            $table->date('end_date')->nullable();
            $table->foreignId('winner_user_id')->nullable()->constrained('users')->onDelete('set null');
            $table->enum('status', ['active', 'completed'])->default('active');
            $table->timestamps();
            $table->timestamp('completed_at')->nullable();
            
            $table->index(['group_id', 'status'], 'idx_group_status');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('games');
    }
};
