<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('games', function (Blueprint $table) {
            $table->id();
            $table->foreignId('group_id')->constrained()->cascadeOnDelete();

            // '50_states' (Build 87a) | 'road_rally' (Build 87b — placeholder)
            $table->string('type', 20)->default('50_states');

            $table->char('country', 2)->default('US'); // 'US' = 50 states | 'CA' = 13 provinces
            $table->string('status', 20)->default('active'); // 'active' | 'completed'

            $table->foreignId('winner_id')->nullable()->constrained('users')->nullOnDelete();
            $table->unsignedInteger('target_count')->default(50); // 50 for US, 13 for CA

            $table->timestamp('started_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('games');
    }
};
