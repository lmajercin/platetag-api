<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Adds 'distance' to the badges.type enum.
 * Includes all previously known values (geographic, milestone, collection,
 * alpca, group) so the MODIFY COLUMN is safe regardless of prior state.
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::statement("ALTER TABLE badges MODIFY COLUMN type ENUM('geographic','milestone','collection','alpca','group','distance') NOT NULL");
    }

    public function down(): void
    {
        DB::statement("ALTER TABLE badges MODIFY COLUMN type ENUM('geographic','milestone','collection','alpca','group') NOT NULL");
    }
};
