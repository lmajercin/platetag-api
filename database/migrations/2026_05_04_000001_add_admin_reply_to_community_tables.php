<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('plate_requests', function (Blueprint $table) {
            $table->text('admin_reply')->nullable()->after('admin_notes');
        });

        Schema::table('bug_reports', function (Blueprint $table) {
            $table->text('admin_reply')->nullable()->after('admin_notes');
        });
    }

    public function down(): void
    {
        Schema::table('plate_requests', function (Blueprint $table) {
            $table->dropColumn('admin_reply');
        });

        Schema::table('bug_reports', function (Blueprint $table) {
            $table->dropColumn('admin_reply');
        });
    }
};
