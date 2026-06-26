<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('social_accounts', function (Blueprint $table) {
            // Encrypted Apple refresh token — used to revoke Apple Sign In on account deletion.
            // Must be `text` not `string` — the encrypted payload exceeds varchar(255).
            // Only populated for provider='apple'. NULL for google/facebook.
            $table->text('apple_refresh_token')->nullable()->after('token_expires_at');
        });
    }

    public function down(): void
    {
        Schema::table('social_accounts', function (Blueprint $table) {
            $table->dropColumn('apple_refresh_token');
        });
    }
};
