<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement("ALTER TABLE badges MODIFY COLUMN type ENUM('geographic', 'milestone', 'collection', 'alpca') NOT NULL");
    }

    public function down(): void
    {
        DB::statement("ALTER TABLE badges MODIFY COLUMN type ENUM('geographic', 'milestone', 'collection') NOT NULL");
    }
};
