<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->boolean('is_alpca_winner')->default(false)->after('is_secondary');
        });
    }

    public function down(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->dropColumn('is_alpca_winner');
        });
    }
};
