<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('mobile_otp_resets', function (Blueprint $table) {
            $table->id();
            $table->string('email')->index();
            $table->string('otp_hash');          // bcrypt of the 6-digit code
            $table->timestamp('expires_at');
            $table->timestamp('created_at')->useCurrent();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('mobile_otp_resets');
    }
};
