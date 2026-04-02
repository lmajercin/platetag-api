<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Carbon;

class RegionSeeder extends Seeder
{
    public function run(): void
    {
        $now = Carbon::now();

        $regions = [];

        // ── United States (50 states + DC) ──────────────────────────────────
        $usStates = [
            ['Alabama',              'AL', 'Montgomery'],
            ['Alaska',               'AK', 'Juneau'],
            ['Arizona',              'AZ', 'Phoenix'],
            ['Arkansas',             'AR', 'Little Rock'],
            ['California',           'CA', 'Sacramento'],
            ['Colorado',             'CO', 'Denver'],
            ['Connecticut',          'CT', 'Hartford'],
            ['Delaware',             'DE', 'Dover'],
            ['District of Columbia', 'DC', 'Washington'],
            ['Florida',              'FL', 'Tallahassee'],
            ['Georgia',              'GA', 'Atlanta'],
            ['Hawaii',               'HI', 'Honolulu'],
            ['Idaho',                'ID', 'Boise'],
            ['Illinois',             'IL', 'Springfield'],
            ['Indiana',              'IN', 'Indianapolis'],
            ['Iowa',                 'IA', 'Des Moines'],
            ['Kansas',               'KS', 'Topeka'],
            ['Kentucky',             'KY', 'Frankfort'],
            ['Louisiana',            'LA', 'Baton Rouge'],
            ['Maine',                'ME', 'Augusta'],
            ['Maryland',             'MD', 'Annapolis'],
            ['Massachusetts',        'MA', 'Boston'],
            ['Michigan',             'MI', 'Lansing'],
            ['Minnesota',            'MN', 'Saint Paul'],
            ['Mississippi',          'MS', 'Jackson'],
            ['Missouri',             'MO', 'Jefferson City'],
            ['Montana',              'MT', 'Helena'],
            ['Nebraska',             'NE', 'Lincoln'],
            ['Nevada',               'NV', 'Carson City'],
            ['New Hampshire',        'NH', 'Concord'],
            ['New Jersey',           'NJ', 'Trenton'],
            ['New Mexico',           'NM', 'Santa Fe'],
            ['New York',             'NY', 'Albany'],
            ['North Carolina',       'NC', 'Raleigh'],
            ['North Dakota',         'ND', 'Bismarck'],
            ['Ohio',                 'OH', 'Columbus'],
            ['Oklahoma',             'OK', 'Oklahoma City'],
            ['Oregon',               'OR', 'Salem'],
            ['Pennsylvania',         'PA', 'Harrisburg'],
            ['Rhode Island',         'RI', 'Providence'],
            ['South Carolina',       'SC', 'Columbia'],
            ['South Dakota',         'SD', 'Pierre'],
            ['Tennessee',            'TN', 'Nashville'],
            ['Texas',                'TX', 'Austin'],
            ['Utah',                 'UT', 'Salt Lake City'],
            ['Vermont',              'VT', 'Montpelier'],
            ['Virginia',             'VA', 'Richmond'],
            ['Washington',           'WA', 'Olympia'],
            ['West Virginia',        'WV', 'Charleston'],
            ['Wisconsin',            'WI', 'Madison'],
            ['Wyoming',              'WY', 'Cheyenne'],
        ];

        foreach ($usStates as [$name, $code, $capital]) {
            $regions[] = [
                'name'         => $name,
                'code'         => $code,
                'country_code' => 'US',
                'capital_city' => $capital,
                'is_active'    => 1,
                'created_at'   => $now,
                'updated_at'   => $now,
            ];
        }

        // ── Canada (10 provinces + 3 territories) ───────────────────────────
        $caRegions = [
            ['Alberta',                  'AB', 'Edmonton'],
            ['British Columbia',         'BC', 'Victoria'],
            ['Manitoba',                 'MB', 'Winnipeg'],
            ['New Brunswick',            'NB', 'Fredericton'],
            ['Newfoundland and Labrador','NL', 'St. John\'s'],
            ['Northwest Territories',    'NT', 'Yellowknife'],
            ['Nova Scotia',              'NS', 'Halifax'],
            ['Nunavut',                  'NU', 'Iqaluit'],
            ['Ontario',                  'ON', 'Toronto'],
            ['Prince Edward Island',     'PE', 'Charlottetown'],
            ['Quebec',                   'QC', 'Quebec City'],
            ['Saskatchewan',             'SK', 'Regina'],
            ['Yukon',                    'YT', 'Whitehorse'],
        ];

        foreach ($caRegions as [$name, $code, $capital]) {
            $regions[] = [
                'name'         => $name,
                'code'         => 'CA-' . $code,
                'country_code' => 'CA',
                'capital_city' => $capital,
                'is_active'    => 1,
                'created_at'   => $now,
                'updated_at'   => $now,
            ];
        }

        // ── Mexico (31 states + Ciudad de México) ───────────────────────────
        $mxStates = [
            ['Aguascalientes',      'MX-AGS',  'Aguascalientes'],
            ['Baja California',     'MX-BC',   'Mexicali'],
            ['Baja California Sur', 'MX-BCS',  'La Paz'],
            ['Campeche',            'MX-CAM',  'Campeche'],
            ['Chiapas',             'MX-CHIS', 'Tuxtla Gutiérrez'],
            ['Chihuahua',           'MX-CHIH', 'Chihuahua'],
            ['Ciudad de México',    'MX-CDMX', 'Mexico City'],
            ['Coahuila',            'MX-COAH', 'Saltillo'],
            ['Colima',              'MX-COL',  'Colima'],
            ['Durango',             'MX-DGO',  'Durango'],
            ['Guanajuato',          'MX-GTO',  'Guanajuato'],
            ['Guerrero',            'MX-GRO',  'Chilpancingo'],
            ['Hidalgo',             'MX-HGO',  'Pachuca'],
            ['Jalisco',             'MX-JAL',  'Guadalajara'],
            ['México',              'MX-MEX',  'Toluca'],
            ['Michoacán',           'MX-MICH', 'Morelia'],
            ['Morelos',             'MX-MOR',  'Cuernavaca'],
            ['Nayarit',             'MX-NAY',  'Tepic'],
            ['Nuevo León',          'MX-NL',   'Monterrey'],
            ['Oaxaca',              'MX-OAX',  'Oaxaca'],
            ['Puebla',              'MX-PUE',  'Puebla'],
            ['Querétaro',           'MX-QRO',  'Querétaro'],
            ['Quintana Roo',        'MX-QROO', 'Chetumal'],
            ['San Luis Potosí',     'MX-SLP',  'San Luis Potosí'],
            ['Sinaloa',             'MX-SIN',  'Culiacán'],
            ['Sonora',              'MX-SON',  'Hermosillo'],
            ['Tabasco',             'MX-TAB',  'Villahermosa'],
            ['Tamaulipas',          'MX-TAMS', 'Ciudad Victoria'],
            ['Tlaxcala',            'MX-TLAX', 'Tlaxcala'],
            ['Veracruz',            'MX-VER',  'Xalapa'],
            ['Yucatán',             'MX-YUC',  'Mérida'],
            ['Zacatecas',           'MX-ZAC',  'Zacatecas'],
        ];

        foreach ($mxStates as [$name, $code, $capital]) {
            $regions[] = [
                'name'         => $name,
                'code'         => $code,
                'country_code' => 'MX',
                'capital_city' => $capital,
                'is_active'    => 1,
                'created_at'   => $now,
                'updated_at'   => $now,
            ];
        }

        DB::table('regions')->insert($regions);

        $this->command->info('Regions seeded: ' . count($regions) . ' rows (US: 51, CA: 13, MX: 32)');
    }
}
