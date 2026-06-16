<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class BadgesSeeder extends Seeder
{
    public function run(): void
    {
        // Geographic badge definitions: slug => [name, description, icon, sort_order, state_codes[]]
        // State codes match the `code` column in the regions table (2-letter US abbreviations).
        $geographic = [
            [
                'slug'        => 'west-coast',
                'name'        => 'West Coast',
                'description' => 'Discover a plate from Washington, Oregon, and California.',
                'icon'        => 'Waves',
                'sort_order'  => 10,
                'states'      => ['WA', 'OR', 'CA'],
            ],
            [
                'slug'        => 'pacific-ocean',
                'name'        => 'Pacific Ocean',
                'description' => 'Discover plates from all five Pacific-bordering states.',
                'icon'        => 'Anchor',
                'sort_order'  => 20,
                'states'      => ['WA', 'OR', 'CA', 'AK', 'HI'],
            ],
            [
                'slug'        => 'thirteen-colonies',
                'name'        => 'Thirteen Colonies',
                'description' => 'Discover a plate from each of the original thirteen colonies.',
                'icon'        => 'Star',
                'sort_order'  => 30,
                'states'      => ['NH', 'MA', 'RI', 'CT', 'NY', 'NJ', 'PA', 'DE', 'MD', 'VA', 'NC', 'SC', 'GA'],
            ],
            [
                'slug'        => 'new-england',
                'name'        => 'New England',
                'description' => 'Discover a plate from all six New England states.',
                'icon'        => 'Tree',
                'sort_order'  => 40,
                'states'      => ['ME', 'NH', 'VT', 'MA', 'RI', 'CT'],
            ],
            [
                'slug'        => 'great-lakes',
                'name'        => 'Great Lakes',
                'description' => 'Discover plates from all eight Great Lakes states.',
                'icon'        => 'Drop',
                'sort_order'  => 50,
                'states'      => ['MN', 'WI', 'IL', 'IN', 'MI', 'OH', 'PA', 'NY'],
            ],
            [
                'slug'        => 'four-corners',
                'name'        => 'Four Corners',
                'description' => 'Discover plates from the four states that meet at a single point.',
                'icon'        => 'Crosshair',
                'sort_order'  => 60,
                'states'      => ['AZ', 'UT', 'CO', 'NM'],
            ],
            [
                'slug'        => 'louisiana-purchase',
                'name'        => 'Louisiana Purchase',
                'description' => 'Discover plates from the fifteen states carved from the Louisiana Purchase territory.',
                'icon'        => 'MapTrifold',
                'sort_order'  => 70,
                'states'      => ['AR', 'MO', 'IA', 'MN', 'ND', 'SD', 'NE', 'KS', 'OK', 'TX', 'NM', 'CO', 'WY', 'MT', 'LA'],
            ],
            [
                'slug'        => 'mississippi-river',
                'name'        => 'Mississippi River',
                'description' => 'Discover plates from all ten states along the Mississippi River.',
                'icon'        => 'NavigationArrow',
                'sort_order'  => 80,
                'states'      => ['MN', 'WI', 'IA', 'IL', 'MO', 'KY', 'TN', 'AR', 'MS', 'LA'],
            ],
            [
                'slug'        => 'appalachia',
                'name'        => 'Appalachia',
                'description' => 'Discover plates from the thirteen Appalachian states.',
                'icon'        => 'Mountains',
                'sort_order'  => 90,
                'states'      => ['PA', 'MD', 'WV', 'VA', 'KY', 'TN', 'NC', 'SC', 'GA', 'AL', 'MS', 'NY', 'OH'],
            ],
            [
                'slug'        => 'gulf-coast',
                'name'        => 'Gulf Coast',
                'description' => 'Discover plates from all five Gulf Coast states.',
                'icon'        => 'Sun',
                'sort_order'  => 100,
                'states'      => ['TX', 'LA', 'MS', 'AL', 'FL'],
            ],
            [
                'slug'        => 'new-states',
                'name'        => '"New"',
                'description' => 'Discover plates from the four states that couldn\'t be bothered to think of an original name.',
                'icon'        => 'Sparkle',
                'sort_order'  => 110,
                'states'      => ['NY', 'NJ', 'NH', 'NM'],
            ],
            [
                'slug'        => 'directionals',
                'name'        => 'Directionals',
                'description' => 'Discover plates from the five states with a compass direction in their name.',
                'icon'        => 'Compass',
                'sort_order'  => 120,
                'states'      => ['SC', 'SD', 'NC', 'ND', 'WV'],
            ],
            [
                'slug'        => 'oregon-trail',
                'name'        => 'Oregon Trail',
                'description' => 'Follow the trail — discover plates from all seven Oregon Trail states.',
                'icon'        => 'Path',
                'sort_order'  => 130,
                'states'      => ['MO', 'KS', 'NE', 'WY', 'ID', 'OR', 'WA'],
            ],
            [
                'slug'        => 'grand-army',
                'name'        => 'The Grand Army of the Republic',
                'description' => 'Discover plates from the seventeen Union states.',
                'icon'        => 'Flag',
                'sort_order'  => 140,
                'states'      => ['ME', 'NH', 'VT', 'MA', 'CT', 'RI', 'NY', 'NJ', 'PA', 'OH', 'IN', 'IL', 'MI', 'WI', 'MN', 'IA', 'KS'],
            ],
            [
                'slug'        => 'rocky-mountains',
                'name'        => 'Rocky Mountains',
                'description' => 'Discover plates from all eight Rocky Mountain states.',
                'icon'        => 'Mountains',
                'sort_order'  => 150,
                'states'      => ['MT', 'ID', 'WY', 'NV', 'UT', 'CO', 'AZ', 'NM'],
            ],
            [
                'slug'        => 'mmmbop',
                'name'        => 'mmmBop',
                'description' => 'Discover plates from all eight states beginning with the letter M.',
                'icon'        => 'MusicNote',
                'sort_order'  => 160,
                'states'      => ['ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT'],
            ],
            [
                'slug'        => 'bottom-five',
                'name'        => 'The Bottom 5',
                'description' => 'Discover plates from the five least-populated states in the country.',
                'icon'        => 'ChartBar',
                'sort_order'  => 170,
                'states'      => ['WY', 'VT', 'AK', 'ND', 'SD'],
            ],
            [
                'slug'        => 'say-aaahhh',
                'name'        => 'Say Aaahhh',
                'description' => 'Discover plates from all four states that begin with the letter A.',
                'icon'        => 'Stethoscope',
                'sort_order'  => 180,
                'states'      => ['AL', 'AK', 'AZ', 'AR'],
            ],
            [
                'slug'        => 'all-vowel',
                'name'        => 'All Vowel Award',
                'description' => 'Discover plates from all eight states whose name begins with a vowel.',
                'icon'        => 'TextAa',
                'sort_order'  => 190,
                'states'      => ['AL', 'AK', 'AZ', 'AR', 'OH', 'OK', 'OR', 'UT'],
            ],
            [
                'slug'        => 'island-fever',
                'name'        => 'Island Fever',
                'description' => 'Discover plates from Hawaii and Rhode Island.',
                'icon'        => 'Island',
                'sort_order'  => 200,
                'states'      => ['HI', 'RI'],
            ],
            [
                'slug'        => 'girls-just-wanna-have-fun',
                'name'        => 'Girls Just Wanna Have Fun',
                'description' => 'Discover plates from all eight states with a girl\'s name.',
                'icon'        => 'Heart',
                'sort_order'  => 210,
                'states'      => ['GA', 'VA', 'NC', 'SC', 'MD', 'MT', 'ND', 'SD'],
            ],
            [
                'slug'        => 'corn-country',
                'name'        => 'Corn Country',
                'description' => 'Discover plates from the top five corn-producing states.',
                'icon'        => 'Plant',
                'sort_order'  => 220,
                'states'      => ['IA', 'IL', 'NE', 'MN', 'IN'],
            ],
            [
                'slug'        => 'amber-waves',
                'name'        => 'Amber Waves',
                'description' => 'Discover plates from the top five wheat-producing states.',
                'icon'        => 'Wheat',
                'sort_order'  => 230,
                'states'      => ['KS', 'ND', 'WA', 'MT', 'OK'],
            ],
            [
                'slug'        => 'atlantic-seaboard',
                'name'        => 'Atlantic Seaboard',
                'description' => 'Discover plates from all fourteen Atlantic Seaboard states.',
                'icon'        => 'Lighthouse',
                'sort_order'  => 240,
                'states'      => ['ME', 'NH', 'MA', 'RI', 'CT', 'NY', 'NJ', 'DE', 'MD', 'VA', 'NC', 'SC', 'GA', 'FL'],
            ],
            [
                'slug'        => 'route-66',
                'name'        => 'Route 66',
                'description' => 'Discover plates from all eight states along the Mother Road.',
                'icon'        => 'Road',
                'sort_order'  => 250,
                'states'      => ['IL', 'MO', 'KS', 'OK', 'TX', 'NM', 'AZ', 'CA'],
            ],
        ];

        // Milestone badge definitions: slug => [name, description, icon, sort_order, threshold]
        $milestones = [
            [
                'slug'        => 'rubber-side-down',
                'name'        => 'Rubber Side Down',
                'description' => 'Discover your first 5 plates.',
                'icon'        => 'Car',
                'sort_order'  => 300,
                'threshold'   => 5,
            ],
            [
                'slug'        => 'license-to-thrill',
                'name'        => 'License to Thrill',
                'description' => 'Discover 10 plates.',
                'icon'        => 'IdentificationCard',
                'sort_order'  => 310,
                'threshold'   => 10,
            ],
            [
                'slug'        => 'going-places',
                'name'        => 'Going Places',
                'description' => 'Discover 50 plates.',
                'icon'        => 'ArrowRight',
                'sort_order'  => 320,
                'threshold'   => 50,
            ],
            [
                'slug'        => 'century-drive',
                'name'        => 'Century Drive',
                'description' => 'Discover 100 plates.',
                'icon'        => 'Medal',
                'sort_order'  => 330,
                'threshold'   => 100,
            ],
            [
                'slug'        => 'road-warrior',
                'name'        => 'Road Warrior',
                'description' => 'Discover 250 plates.',
                'icon'        => 'Shield',
                'sort_order'  => 340,
                'threshold'   => 250,
            ],
            [
                'slug'        => 'indianapolis',
                'name'        => 'Indianapolis',
                'description' => 'Discover 500 plates.',
                'icon'        => 'Trophy',
                'sort_order'  => 350,
                'threshold'   => 500,
            ],
            [
                'slug'        => 'the-grand-tour',
                'name'        => 'The Grand Tour',
                'description' => 'Discover 1,000 plates.',
                'icon'        => 'GlobeHemisphereWest',
                'sort_order'  => 360,
                'threshold'   => 1000,
            ],
        ];

        // Build a code→id lookup for US regions
        $regionMap = DB::table('regions')
            ->where('country_code', 'US')
            ->pluck('id', 'code')
            ->all();

        // Insert geographic badges
        foreach ($geographic as $def) {
            $badgeId = DB::table('badges')->insertGetId([
                'slug'        => $def['slug'],
                'name'        => $def['name'],
                'description' => $def['description'],
                'type'        => 'geographic',
                'threshold'   => null,
                'icon'        => $def['icon'],
                'sort_order'  => $def['sort_order'],
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ]);

            $pivotRows = [];
            foreach ($def['states'] as $code) {
                if (!isset($regionMap[$code])) {
                    throw new \RuntimeException("BadgesSeeder: region code '{$code}' not found in regions table.");
                }
                $pivotRows[] = ['badge_id' => $badgeId, 'region_id' => $regionMap[$code]];
            }
            DB::table('badge_regions')->insert($pivotRows);
        }

        // Insert milestone badges
        foreach ($milestones as $def) {
            DB::table('badges')->insert([
                'slug'        => $def['slug'],
                'name'        => $def['name'],
                'description' => $def['description'],
                'type'        => 'milestone',
                'threshold'   => $def['threshold'],
                'icon'        => $def['icon'],
                'sort_order'  => $def['sort_order'],
                'is_active'   => true,
                'created_at'  => now(),
                'updated_at'  => now(),
            ]);
        }
    }
}
