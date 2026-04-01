<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('series', function (Blueprint $table) {
            // Drop category_id FK + column — Category lives on Plate only
            $table->dropConstrainedForeignId('category_id');

            // Denormalized country_code for filterable dropdowns without full join
            $table->string('country_code', 10)->default('US')->after('region_id');

            // Design template fields
            $table->string('background', 255)->nullable()->after('country_code');
            $table->string('header', 255)->nullable()->after('background');
            $table->string('footer', 255)->nullable()->after('header');
            $table->string('digits_style', 100)->nullable()->after('footer');

            // Replace description with notes
            $table->text('notes')->nullable()->after('digits_style');
            $table->dropColumn('description');

            // Series base image
            $table->string('image_filename', 255)->nullable()->after('is_active');
        });
    }

    public function down(): void
    {
        Schema::table('series', function (Blueprint $table) {
            $table->dropColumn(['country_code', 'background', 'header', 'footer', 'digits_style', 'notes', 'image_filename']);
            $table->text('description')->nullable();
            $table->foreignId('category_id')->nullable()->constrained()->nullOnDelete();
        });
    }
};

