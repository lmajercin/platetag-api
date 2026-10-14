<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('games', function (Blueprint $table) {
            // Road Rally date window
            $table->date('start_date')->nullable()->after('target_count');
            $table->date('end_date')->nullable()->after('start_date');

            // Dual winners (Road Rally only; 50 States continues to use winner_id)
            $table->foreignId('winner_plates_user_id')
                ->nullable()
                ->after('end_date')
                ->constrained('users')
                ->nullOnDelete();

            $table->foreignId('winner_states_user_id')
                ->nullable()
                ->after('winner_plates_user_id')
                ->constrained('users')
                ->nullOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('games', function (Blueprint $table) {
            $table->dropForeign(['winner_plates_user_id']);
            $table->dropForeign(['winner_states_user_id']);
            $table->dropColumn(['start_date', 'end_date', 'winner_plates_user_id', 'winner_states_user_id']);
        });
    }
};
