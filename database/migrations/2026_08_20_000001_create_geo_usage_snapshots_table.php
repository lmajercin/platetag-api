<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('geo_usage_snapshots', function (Blueprint $table) {
            $table->id();
            $table->date('snapshot_date')->unique();
            $table->unsignedInteger('discoveries_total')->default(0);
            $table->unsignedInteger('discoveries_with_location')->default(0);
            $table->unsignedInteger('discoveries_without_location')->default(0);
            $table->unsignedInteger('active_users')->default(0);
            $table->unsignedInteger('users_with_location')->default(0);
            $table->unsignedInteger('users_without_location')->default(0);
            // Percentages stored for fast charting (0–100, one decimal via float)
            $table->decimal('pct_discoveries_with_location', 5, 2)->default(0);
            $table->decimal('pct_users_with_location', 5, 2)->default(0);
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('geo_usage_snapshots');
    }
};
