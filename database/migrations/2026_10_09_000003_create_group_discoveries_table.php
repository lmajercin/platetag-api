<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('group_discoveries', function (Blueprint $table) {
            $table->id();
            $table->foreignId('group_id')->constrained()->cascadeOnDelete();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->foreignId('plate_id')->constrained()->cascadeOnDelete();
            $table->timestamp('discovered_at'); // server-enforced — never client-supplied

            $table->timestamps();

            // Prevent duplicate attribution for the same plate per user per group
            $table->unique(['group_id', 'user_id', 'plate_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('group_discoveries');
    }
};
