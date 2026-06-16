<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class CategorySeeder extends Seeder
{
    public function run(): void
    {
        DB::table('categories')->truncate();

        $categories = [
            ['name' => 'Standard Issue',             'description' => 'Default passenger plate issued by the region'],
            ['name' => 'School',                      'description' => 'All educational institutions: K-12, high schools, colleges, universities, seminaries, law schools'],
            ['name' => 'Military / Veteran',          'description' => 'Active duty, veteran, and branch-specific plates'],
            ['name' => 'Dealer / Manufacturer',       'description' => 'Dealer, manufacturer, and transporter plates'],
            ['name' => 'Disabled / Accessibility',    'description' => 'Disabled person and accessibility designation plates'],
            ['name' => 'Government / Exempt',         'description' => 'Government agency, exempt, and official use plates'],
            ['name' => 'First Responder',             'description' => 'Police, fire, EMS, sheriff, ambulance, Civil Air Patrol, hook & ladder companies'],
            ['name' => 'Conservation / Environment',  'description' => 'Wildlife, parks, nature trusts, and environmental causes'],
            ['name' => 'Health & Awareness',          'description' => 'Breast cancer, sickle cell, CASA, child abuse prevention, and other health causes'],
            ['name' => 'Sports Team',                 'description' => 'Professional and collegiate sports team plates'],
            ['name' => 'Arts / Culture',              'description' => 'Museums, arts councils, humanities, and cultural organizations'],
            ['name' => 'Agricultural',                'description' => 'Farming and ranching plates (distinct from Specialty Equipment vehicle class)'],
            ['name' => 'Fraternal / Civic',           'description' => 'Masons, Eagles, Rotary, VFW, Elks, and similar organizations'],
            ['name' => 'Historical / Commemorative',  'description' => 'Anniversary, historical event, and commemorative plates'],
            ['name' => 'Radio / Amateur Radio',       'description' => 'Citizens Band (CB) and Amateur (HAM) radio operator plates'],
            ['name' => 'Other / Specialty',           'description' => 'Catch-all for plates that do not fit another category'],
        ];

        foreach ($categories as $cat) {
            DB::table('categories')->insert([
                'name'        => $cat['name'],
                'slug'        => Str::slug($cat['name']),
                'description' => $cat['description'],
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ]);
        }
    }
}
