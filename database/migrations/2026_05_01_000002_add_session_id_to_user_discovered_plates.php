<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('user_discovered_plates', function (Blueprint $table) {
            $table->foreignId('session_id')
                ->nullable()
                ->default(null)
                ->after('id')
                ->constrained('discovery_sessions')
                ->nullOnDelete();

            $table->index('session_id');
        });
    }

    public function down(): void
    {
        Schema::table('user_discovered_plates', function (Blueprint $table) {
            $table->dropForeign(['session_id']);
            $table->dropIndex(['session_id']);
            $table->dropColumn('session_id');
        });
    }
};
