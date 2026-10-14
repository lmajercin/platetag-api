<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Data migration — inserts the two Road Rally badge definitions.
 * Uses insertOrIgnore so re-running is safe.
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::table('badges')->insertOrIgnore([
            [
                'slug'        => 'road_rally_most_plates',
                'name'        => 'Road Rally: Top Collector',
                'description' => 'Logged the most unique plates during a Road Rally.',
                'type'        => 'group',
                'threshold'   => 0,
                'icon'        => 'flag-banner',   // matches phosphor icon used in mobile UI
                'sort_order'  => 999,
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ],
            [
                'slug'        => 'road_rally_most_states',
                'name'        => 'Road Rally: State Chaser',
                'description' => 'Covered the most states during a Road Rally.',
                'type'        => 'group',
                'threshold'   => 0,
                'icon'        => 'map-pin',       // matches phosphor icon used in mobile UI
                'sort_order'  => 1000,
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ],
        ]);
    }

    public function down(): void
    {
        DB::table('badges')->whereIn('slug', [
            'road_rally_most_plates',
            'road_rally_most_states',
        ])->delete();
    }
};
