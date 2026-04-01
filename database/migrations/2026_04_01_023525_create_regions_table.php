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
        Schema::create('regions', function (Blueprint $table) {
            $table->id();
            $table->string('name', 191)->unique();
            $table->string('code', 10)->unique();  // e.g. US-CA, CA-ON
            $table->string('country_code', 10)->default('US');
            $table->string('capital_city', 100)->nullable();
            $table->decimal('capital_lat', 10, 7)->nullable();
            $table->decimal('capital_lng', 10, 7)->nullable();
            $table->boolean('is_active')->default(true);
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('regions');
    }
};
