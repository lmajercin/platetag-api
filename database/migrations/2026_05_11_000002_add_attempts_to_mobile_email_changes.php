<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('mobile_email_changes', function (Blueprint $table) {
            $table->tinyInteger('attempts')->default(0)->after('otp_hash');
        });
    }

    public function down(): void
    {
        Schema::table('mobile_email_changes', function (Blueprint $table) {
            $table->dropColumn('attempts');
        });
    }
};
