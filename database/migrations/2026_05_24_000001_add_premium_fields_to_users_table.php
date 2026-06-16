<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->boolean('is_premium')->default(false)->after('is_admin');
            $table->boolean('is_founding_member')->default(false)->after('is_premium');
            $table->timestamp('premium_granted_at')->nullable()->after('is_founding_member');
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->dropColumn(['is_premium', 'is_founding_member', 'premium_granted_at']);
        });
    }
};
