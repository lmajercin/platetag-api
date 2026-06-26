<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->text('ai_detail')->nullable()->after('detail');
            $table->string('ai_tags', 500)->nullable()->after('tags');
            $table->boolean('ai_reviewed')->default(false)->after('ai_tags');
        });
    }

    public function down(): void
    {
        Schema::table('plates', function (Blueprint $table) {
            $table->dropColumn(['ai_detail', 'ai_tags', 'ai_reviewed']);
        });
    }
};
