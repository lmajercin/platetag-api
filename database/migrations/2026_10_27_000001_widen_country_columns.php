<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

// @Audit GO: 2026-10-27 — Build 91. Widen country columns from CHAR(2) to VARCHAR(4)
// to support the new 'both' (US + Canada Challenge) value.
// 'US' (2 chars) and 'CA' (2 chars) are unaffected. 'both' (4 chars) was silently
// truncated to 'bo' under MySQL strict mode before this migration.

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('groups', function (Blueprint $table) {
            $table->string('country', 4)->default('US')->change();
        });

        Schema::table('games', function (Blueprint $table) {
            $table->string('country', 4)->default('US')->change();
        });
    }

    public function down(): void
    {
        Schema::table('groups', function (Blueprint $table) {
            $table->char('country', 2)->default('US')->change();
        });

        Schema::table('games', function (Blueprint $table) {
            $table->char('country', 2)->default('US')->change();
        });
    }
};
