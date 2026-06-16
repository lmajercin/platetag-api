<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Clear seed-only data — schema is incompatible with existing rows
        DB::statement('SET FOREIGN_KEY_CHECKS=0');
        DB::table('plates')->truncate();
        DB::statement('SET FOREIGN_KEY_CHECKS=1');

        Schema::table('plates', function (Blueprint $table) {
            // Drop FK + columns that now live on Series or are redundant
            $table->dropConstrainedForeignId('region_id');
            $table->dropColumn(['state_code', 'country_code', 'plate_type', 'year_introduced', 'year_discontinued']);

            // Plate-level classification and override fields
            $table->string('vehicle_class', 50)->default('Passenger')->after('category_id');
            $table->string('header_override', 255)->nullable()->after('vehicle_class');
            $table->string('footer_override', 255)->nullable()->after('header_override');
            $table->text('detail')->nullable()->after('footer_override');
            $table->string('serial_format', 255)->nullable()->after('detail');
            $table->boolean('updates_complete')->default(false)->after('serial_format');
        });

        // Make series_id NOT NULL — table is empty so no data risk
        Schema::table('plates', function (Blueprint $table) {
            $table->dropForeign(['series_id']);
        });
        DB::statement('ALTER TABLE plates MODIFY series_id BIGINT UNSIGNED NOT NULL');
        Schema::table('plates', function (Blueprint $table) {
            $table->foreign('series_id')->references('id')->on('series')->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->dropColumn(['vehicle_class', 'header_override', 'footer_override', 'detail', 'serial_format', 'updates_complete']);
            $table->string('state_code', 10)->nullable();
            $table->string('country_code', 10)->default('US');
            $table->foreignId('region_id')->nullable()->constrained()->nullOnDelete();
            $table->string('plate_type', 100)->nullable();
            $table->year('year_introduced')->nullable();
            $table->year('year_discontinued')->nullable();
        });
    }
};

