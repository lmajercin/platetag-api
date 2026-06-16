<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table) {
            // Null = no active promo (or permanent paid/founding access).
            // A datetime = windowed promo expiry. When now() > promo_expires_at,
            // the user's promo access has lapsed and they fall back to the free cap.
            // The ExpirePromoAccess command runs nightly and revokes is_premium
            // for users where promo_expires_at < now() AND they have no IAP purchase.
            $table->timestamp('promo_expires_at')->nullable()->after('premium_granted_at');
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->dropColumn('promo_expires_at');
        });
    }
};
