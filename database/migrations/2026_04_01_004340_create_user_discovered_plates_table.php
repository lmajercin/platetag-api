<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('user_discovered_plates', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->foreignId('plate_id')->constrained()->cascadeOnDelete();
            $table->timestamp('discovered_at')->useCurrent();
            $table->string('notes', 500)->nullable();
            $table->unique(['user_id', 'plate_id']); // one discovery record per plate per user
            $table->index('user_id');
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('user_discovered_plates');
    }
};
