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
        Schema::table('user_discovered_plates', function (Blueprint $table) {
            // Drop the one-per-plate unique constraint — re-discovery is now allowed
            $table->dropUnique(['user_id', 'plate_id']);

            // Geolocation at time of discovery
            $table->decimal('latitude',  10, 7)->nullable()->after('notes');
            $table->decimal('longitude', 10, 7)->nullable()->after('latitude');
            $table->string('location_label', 255)->nullable()->after('longitude');

            // Flag the first time a user discovers a particular plate type
            $table->boolean('is_first_discovery')->default(true)->after('location_label');

            // Index for fast collection queries
            $table->index(['user_id', 'plate_id']);
        });
    }

    public function down(): void
    {
        Schema::table('user_discovered_plates', function (Blueprint $table) {
            $table->dropIndex(['user_id', 'plate_id']);
            $table->dropColumn(['latitude', 'longitude', 'location_label', 'is_first_discovery']);
            $table->unique(['user_id', 'plate_id']);
        });
    }
};
