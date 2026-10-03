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
        Schema::create('group_discoveries', function (Blueprint $table) {
            $table->id();
            $table->foreignId('group_id')->constrained('groups')->onDelete('cascade');
            $table->foreignId('user_id')->constrained('users')->onDelete('cascade');
            $table->foreignId('plate_id')->constrained('plates')->onDelete('cascade');
            $table->timestamp('discovered_at');
            
            $table->unique(['group_id', 'user_id', 'plate_id'], 'unique_group_user_plate');
            $table->index(['group_id', 'user_id'], 'idx_group_user');
            $table->index('discovered_at');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('group_discoveries');
    }
};
