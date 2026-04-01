<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class PlatesSeeder extends Seeder
{
    public function run(): void
    {
        $plates = [
            ['state_code' => 'CA', 'country_code' => 'US', 'plate_type' => 'Standard',  'name' => 'California Standard',      'year_introduced' => 2020],
            ['state_code' => 'CA', 'country_code' => 'US', 'plate_type' => 'Specialty', 'name' => 'California Arts Council',   'year_introduced' => 2015],
            ['state_code' => 'NY', 'country_code' => 'US', 'plate_type' => 'Standard',  'name' => 'New York Standard',         'year_introduced' => 2010],
            ['state_code' => 'NY', 'country_code' => 'US', 'plate_type' => 'Specialty', 'name' => 'New York Empire State',     'year_introduced' => 2018],
            ['state_code' => 'TX', 'country_code' => 'US', 'plate_type' => 'Standard',  'name' => 'Texas Standard',            'year_introduced' => 2012],
            ['state_code' => 'FL', 'country_code' => 'US', 'plate_type' => 'Standard',  'name' => 'Florida Standard',          'year_introduced' => 2013],
            ['state_code' => 'ON', 'country_code' => 'CA', 'plate_type' => 'Standard',  'name' => 'Ontario Standard',          'year_introduced' => 2008],
            ['state_code' => 'BC', 'country_code' => 'CA', 'plate_type' => 'Standard',  'name' => 'British Columbia Standard', 'year_introduced' => 2011],
        ];

        $now = now();

        foreach ($plates as $plate) {
            DB::table('plates')->insertOrIgnore([
                'state_code'      => $plate['state_code'],
                'country_code'    => $plate['country_code'],
                'plate_type'      => $plate['plate_type'],
                'name'            => $plate['name'],
                'slug'            => Str::slug($plate['name']),
                'year_introduced' => $plate['year_introduced'],
                'is_active'       => true,
                'created_at'      => $now,
                'updated_at'      => $now,
            ]);
        }
    }
}
