<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Seeds the four Long-Distance badge tiers.
 * threshold = distance in miles from the plate's region capital.
 * Uses insertOrIgnore so re-running is safe.
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::table('badges')->insertOrIgnore([
            [
                'slug'        => 'distance_500',
                'name'        => 'Road Tripper',
                'description' => 'Discovered a plate 500+ miles from its home region.',
                'type'        => 'distance',
                'threshold'   => 500,
                'icon'        => 'map-pin',
                'sort_order'  => 200,
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ],
            [
                'slug'        => 'distance_1000',
                'name'        => 'Road Warrior',
                'description' => 'Discovered a plate 1,000+ miles from its home region.',
                'type'        => 'distance',
                'threshold'   => 1000,
                'icon'        => 'car',
                'sort_order'  => 201,
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ],
            [
                'slug'        => 'distance_2000',
                'name'        => 'Cross-Country',
                'description' => 'Discovered a plate 2,000+ miles from its home region.',
                'type'        => 'distance',
                'threshold'   => 2000,
                'icon'        => 'path',
                'sort_order'  => 202,
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ],
            [
                'slug'        => 'distance_3000',
                'name'        => 'Transcontinental',
                'description' => 'Discovered a plate 3,000+ miles from its home region.',
                'type'        => 'distance',
                'threshold'   => 3000,
                'icon'        => 'airplane-tilt',
                'sort_order'  => 203,
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ],
        ]);
    }

    public function down(): void
    {
        DB::table('badges')->whereIn('slug', [
            'distance_500',
            'distance_1000',
            'distance_2000',
            'distance_3000',
        ])->delete();
    }
};
