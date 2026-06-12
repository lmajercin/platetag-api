<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Add 'collection' to the type enum
        DB::statement("ALTER TABLE badges MODIFY COLUMN type ENUM('geographic', 'milestone', 'collection') NOT NULL");
    }

    public function down(): void
    {
        // Remove 'collection' from the enum (only safe if no badges use it)
        DB::statement("ALTER TABLE badges MODIFY COLUMN type ENUM('geographic', 'milestone') NOT NULL");
    }
};
