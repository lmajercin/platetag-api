<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            // Comma-separated visual feature keywords for user search
            // e.g. "horse, red, mountain, sunset, eagle"
            $table->string('tags', 500)->nullable()->after('detail');
        });
    }

    public function down(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->dropColumn('tags');
        });
    }
};
