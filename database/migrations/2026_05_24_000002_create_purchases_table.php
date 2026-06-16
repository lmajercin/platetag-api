<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('purchases', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            // 'founding' is internal-only — never accepted from client input
            $table->enum('platform', ['apple', 'google', 'stripe', 'founding']);
            $table->string('product_id', 255);
            $table->string('transaction_id', 255);
            // Raw receipt stored encrypted via model cast (see Purchase::casts())
            // LONGTEXT required — Apple receipts can exceed standard VARCHAR limits
            $table->longText('raw_receipt')->nullable();
            $table->timestamp('verified_at')->nullable();
            $table->timestamps();

            // Prevent replay attacks: same transaction on the same platform can only be used once
            $table->unique(['transaction_id', 'platform']);
            $table->index('user_id');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('purchases');
    }
};
