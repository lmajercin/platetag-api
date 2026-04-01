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
        Schema::create('plates', function (Blueprint $table) {
            $table->id();
            $table->string('state_code', 10)->index();      // e.g. "CA", "ON"
            $table->string('country_code', 10)->default('US'); // "US" or "CA"
            $table->string('plate_type', 100);               // e.g. "Standard", "Specialty"
            $table->string('name', 191);                     // display name
            $table->string('slug', 191)->unique();           // url-safe identifier
            $table->string('image_filename', 255)->nullable();
            $table->year('year_introduced')->nullable();
            $table->year('year_discontinued')->nullable();   // null = currently issued
            $table->boolean('is_active')->default(true)->index();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('plates');
    }
};
