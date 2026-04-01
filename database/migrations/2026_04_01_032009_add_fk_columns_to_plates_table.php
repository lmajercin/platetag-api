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
        Schema::table('plates', function (Blueprint $table) {
            $table->foreignId('region_id')->nullable()->after('country_code')->constrained()->nullOnDelete();
            $table->foreignId('category_id')->nullable()->after('region_id')->constrained()->nullOnDelete();
            $table->foreignId('series_id')->nullable()->after('category_id')->constrained()->nullOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->dropForeignIdFor(\App\Models\Region::class);
            $table->dropForeignIdFor(\App\Models\Category::class);
            $table->dropForeignIdFor(\App\Models\Series::class);
        });
    }
};
