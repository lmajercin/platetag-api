#!/usr/bin/env python3
"""
convert_plates_csv.py
=====================
Converts the Keegan/DMV-sourced CSV format into the plates_react bulk import format.

INPUT columns:  State | Description | Plate Image | Source
OUTPUT columns: plate_number | region_name | category_name | series_name |
                description | year_introduced | year_discontinued | is_active |
                plate_header | plate_base | plate_serial | plate_footer |
                image_url | image_filename

Usage:
    python convert_plates_csv.py input.csv output.csv
    python convert_plates_csv.py input.csv output.csv --download-images ./images/ca
    python convert_plates_csv.py input.csv output.csv --state CA   (filter to one state)

Dependencies: none beyond Python 3.7+ standard library.
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── State code → full region name (matches your DB exactly) ───────────────────
STATE_CODE_TO_REGION = {
    'AL': 'Alabama',        'AK': 'Alaska',         'AZ': 'Arizona',
    'AR': 'Arkansas',       'CA': 'California',     'CO': 'Colorado',
    'CT': 'Connecticut',    'DE': 'Delaware',        'DC': 'District of Columbia',
    'FL': 'Florida',        'GA': 'Georgia',         'HI': 'Hawaii',
    'ID': 'Idaho',          'IL': 'Illinois',        'IN': 'Indiana',
    'IA': 'Iowa',           'KS': 'Kansas',          'KY': 'Kentucky',
    'LA': 'Louisiana',      'ME': 'Maine',           'MD': 'Maryland',
    'MA': 'Massachusetts',  'MI': 'Michigan',        'MN': 'Minnesota',
    'MS': 'Mississippi',    'MO': 'Missouri',        'MT': 'Montana',
    'NE': 'Nebraska',       'NV': 'Nevada',          'NH': 'New Hampshire',
    'NJ': 'New Jersey',     'NM': 'New Mexico',      'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota',    'OH': 'Ohio',
    'OK': 'Oklahoma',       'OR': 'Oregon',          'PA': 'Pennsylvania',
    'RI': 'Rhode Island',   'SC': 'South Carolina',  'SD': 'South Dakota',
    'TN': 'Tennessee',      'TX': 'Texas',           'UT': 'Utah',
    'VT': 'Vermont',        'VA': 'Virginia',        'WA': 'Washington',
    'WV': 'West Virginia',  'WI': 'Wisconsin',       'WY': 'Wyoming',
}

# ── California: CSV 3rd-segment variant → DB series name ─────────────────────
# Update these names if you rename a series in your DB.
CA_SERIES_MAP = {
    'block':       'CA02-White/Blue-Passenger-1987',   # series_id=8
    'script':      'CA01-Script-2001',                 # series_id=9
    'sun':         'CA03-Sunset-Passenger-1982',       # series_id=7
    'blue + gold': 'CA04-Blue/Gold-Passenger-1970',    # series_id=6
    'black + gold':'CA05-Black-Gold-Passenger-1963',   # series_id=5
}
CA_SPECIALTY_SERIES = 'CA06-Specialty-2001'  # catch-all for modern CA specialty plates

# ── Category inference rules ──────────────────────────────────────────────────
# Each entry: (keyword_list, category_name)
# Rules are checked in order — first match wins.
# Category names must exactly match your DB categories table.
CATEGORY_RULES = [
    # Veteran / Military
    (['congressional medal of honor', 'medal of honor'],    'Veteran'),
    (['gold star family'],                                   'Veteran'),
    (['legion of valor'],                                    'Veteran'),
    (['memorial', 'war memorial'],                          'Veteran'),
    (['ex-prisoner of war', 'prisoner of war', 'POW',
       'Ex-POW'],                                            'Veteran'),
    (['purple heart', 'combat', 'combat wounded'],           'Veteran'),
    (['valor', 'hero', 'heroes', 'gallantry', 'she served'], 'Veteran'),
    (['air crew', 'commendation', 'merit', 'service', 'distinguished'], 'Veteran'),
    (['disabled veteran'],                                   'Veteran'),
    (['Bronze Star', 'bronze star'],                         'Veteran'),
     (['silver star'],                                       'Veteran'),
     (['Desert Storm', 'desert shield'],                     'Veteran'),
     (['Atomic Veterans', 'atomic veteran'],                 'Veteran'),
    (['pearl harbor'],                                       'Veteran'),
    (['armed forces', 'air force', 'army', 'navy', 'marines', 'coast guard',
      'national guard', 'combat veteran', 'gulf war', 'vietnam', 'korea',
      'wwii', 'world war','Afghanistan Campaign', 'GWOT',
       'Global War on Terror', 'space force'],                'Veteran'),
    (['Expeditionary Medal', 'expeditionary campaign', 'expeditionary'],        'Veteran'),
    (['Iraq war', 'iraq campaign'],                            'Veteran'),
    (['afghanistan war', 'afghanistan campaign'],          'Veteran'),
    (['Iran war', 'iran campaign'],                            'Veteran'),
      (['veteran', 'military'],                                'Veteran'),

    # Government / Official
    (['foreign organization'],                               'Government'),
    (['honorary consul'],                                    'Government'),
    (['justice of the peace', 'justice', 'judge'],           'Government'),
    (['exempt', 'state assembly', 'state senate', 'congressional',
      'government', 'official'],                             'Government'),
      (['police', 'sheriff', 'trooper', 'highway patrol', 'state patrol',
        'department of transportation', 'dot'],             'First Responder'),

    # Dealer / Trade
    (['dismantler'],                                         'Dealer'),
    (['distributor'],                                        'Dealer'),
    (['remanufacturer'],                                     'Dealer'),
    (['manufacturer'],                                       'Dealer'),
    (['dealer'],                                             'Dealer'),

    # Apportioned / Commercial fleet
    (['apportioned', 'prorate', 'irp'],                     'Apportioned'),

    # Radio
    (['amateur radio', 'ham radio'],                        'Radio'),
    (['citizens band', 'cb radio'],                         'Radio'),

    # Schools
    (['university', 'college', 'ucla', 'usc', 'cal state', 'uc ', 'notre dame',
      'stanford', 'tamu', 'texas a&m', 'school'],           'Schools'),
      (['LSU', 'louisiana state university', 'Auburn',
      'Ole Miss', 'Mississippi state', 'Clemson', 'FSU'],   'Schools'),
      (['florida state university', 'florida state', ],   'Schools'),
      (['MIT,', 'massachusetts institute of technology', 'harvard', 'yale',
        'princeton','Rutgers', 'Cornell', 'NYU'],          'Schools'),
      (['University of Michigan', 'Michigan State', 'UMich'], 'Schools'),
      (['University of Texas', 'UT Austin', 'UT'],         'Schools'),
      (['University of California', 'UC Berkeley', 'UCB', 'UC Davis', 'UCD',
        'UC Irvine', 'UCI', 'UC San Diego', 'UCSD', 'UC Santa Cruz',
          'UCSC', 'UC Santa Barbara', 'UCSB','SDSU'], 'Schools'),
      (['University of Florida', 'UF'],                      'Schools'),
       (['University of Georgia', 'UGA'],                      'Schools'),
       (['University of Alabama', 'UA'],                      'Schools'),
      (['elementary', 'middle school', 'high school'],     'Schools'),

    # Sports
    (['olympic', 'olympics'],                                'Sports'),
        (['nfl', 'national football league', 'mlb', 'major league baseball',
        'nba', 'national basketball association', 'nhl', 'hockey'],  'Sports'),
        (['nascar', 'racing', 'race car'],                      'Sports'),
        (['college sports', 'collegiate'],                      'Sports'),
        (['biking', 'cycling', 'bicycle', 'bmx'],               'Sports'),
        (['golf', 'golfing', 'country club'],                   'Sports'),
        (['tennis'],                                            'Sports'),
        (['basketball'],                                        'Sports'),
        (['football'],                                          'Sports'),
        (['baseball', 'little league', 'babe ruth'],            'Sports'),
        (['hockey'],                                            'Sports'),
        (['soccer'],                                            'Sports'),
        (['surfer', 'surfing', 'swimming', 'swim team'],        'Sports'),

    # Civic / Social awareness (before Outdoors to catch wildlife causes too)
    (['firefighter', 'fire fighter'],                        ''),
    (['breast cancer', 'pink ribbon'],                       'Health'),
    (['cancer', 'cancer society','cancer awareness'],        'Health'),
    (['domestic violence', 'dv awareness'],                  'Civic'),
    (['kids', 'children', 'child', 'youth'],                 'Civic'),
    (['autism', 'autistic'],                                 'Health'),
    (['cystic fibrosis', 'cf foundation'],                   'Health'),
    (['epilepsy', 'epilepsy foundation'],                    'Health'),
    (['spay/neuter', 'spay', 'neuter', 'pet population'],    'Civic'),
    (['freemason', 'masonic', 'grand hall', 'masons'],       'Civic'),
    (['sons of confederate veterans', 'scv'],                'Civic'),
    (['daughters of the american revolution', 'dar'],        'Civic'),
    (['kiwanis', 'lions club', 'rotary club'],               'Civic'),
    (['heart disease', 'heart foundation'],                  'Health'),
    (['Shriners', 'Ronald McDonald House'],                  'Civic'),
    (['St Jude', 'st jude'],                                 'Civic'),
    (['Kofc', 'knights of columbus'],                        'Civic'),
    (['habitat for humanity'],                               'Civic'),
    (['diabetes', 'diabetic', 'juvenile diabetes'],          'Health'),
    (['multiple sclerosis', 'ms society'],                   'Health'),
    (['arts', 'museum', 'snoopy'],                           'Civic'),
    (['pet lovers', 'animal'],                               'Civic'),
    (['organ donation', 'organ donor'],                      'Health'),
    (['bicentennial'],                                       'Civic'),
    (['association', 'foundation', 'society'],               'Civic'),
    (['alumni', 'alumnus', 'alumna'],                        'Civic'),
    (['fraternity', 'sorority'],                             'Civic'),

    # Outdoors / Conservation
    (['wildlife', 'conservation', 'environmental', 'env license',
      'nature', 'parks', 'forest', 'salmon', 'orca', 'eagle',
      'whale', 'fish'],                                     'Outdoors'),
      (['Ducks Unlimited', 'ducks unlimited', 'ducks'],     'Outdoors'),
      (['turkey', 'pheasant', 'quail', 'waterfowl'],        'Outdoors'),
      (['hunting', 'fish and wildlife',],                   'Outdoors'),
      (['fishing', 'fishing and wildlife', ],               'Outdoors'),
      (['boating', 'watercraft', 'marine', 'yacht', 'sailing',
       'kayaking', 'yacht club', 'yachting'],               'Outdoors'),

    # Vintage / Classic
    (['horseless carriage', 'vintage', 'motorsports'],         'Vintage'),
    (['antique', 'historical vehicle', 'historic vehicle',
      'classic', 'legacy', '1960','hot rod', 'cruisers'],      'Vintage'),

    # Handicapped
    (['disabled person'],                                    'Handicapped'),

    # Occupational
    (['press photographer', 'press'],                          'Occupational'),
    (['home builders', 'home builder'],                        'Occupational'),
    (['pastor, clergy', 'priest', 'minister', 'rabbi'],        'Occupational'),
    (['letter carrier', 'postal worker', 'mail carrier'],      'Occupational'),
    (['livery', 'taxi', 'chauffeur'],                          'Occupational'),
    (['physician', 'doctor', 'veterinarian'],                  'Occupational'),
    (['farm', 'farmer','agriculture','agricultural'],          'Occupational'),

    # Commercial = Standard base
    (['commercial motor vehicle'],                           'Standard'), 

    # Specialty Equipment / Trailers
    (['permanent trailer', 'trailer', 'special equipment', 'moped'],
                                                            'Specialty Equip'),
    (['bus', 'motorhome', 'motor home', 'rv', 'recreational vehicle'], 'Specialty Equip'),

    # Fallback
]
DEFAULT_CATEGORY = 'Standard'


def infer_category(plate_name):
    """Return the best-matching category name for the given plate name."""
    name_lower = plate_name.lower()
    for keywords, category in CATEGORY_RULES:
        if any(kw in name_lower for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def extract_image_url(cell):
    """Extract URL from markdown ![Plate](URL) syntax, or return raw if plain URL."""
    m = re.search(r'!\[.*?\]\((.*?)\)', cell)
    if m:
        return m.group(1).strip()
    cell = cell.strip()
    if cell.startswith('http'):
        return cell
    return ''


def url_to_safe_filename(url, state_code, plate_slug):
    """Build a local filename: state-plateslug.ext (e.g. ca-amateur-radio-block.gif)
    plate_slug already contains the state prefix so we strip it before prepending.
    """
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower() or '.jpg'
    # Sanitize slug: lowercase, replace non-alphanumeric with dash
    slug = re.sub(r'[^a-z0-9]+', '-', plate_slug.lower()).strip('-')
    # Remove leading "xx-" prefix if the slug starts with the state code already
    prefix = state_code.lower() + '-'
    if slug.startswith(prefix):
        slug = slug[len(prefix):]
    slug = slug[:60]  # cap length
    return f"{state_code.lower()}-{slug}{ext}"


def parse_description(state_code, description):
    """
    Parse the Description column into (plate_name, series_name).

    Input examples:
      "California - Amateur Radio Call Letters - Block"
      "California - ARTS"
      "Rhode Island - Beavertail Lighthouse"
      "California - New Vehicle Distributor - Motorcycle, Blue + Gold"

    Returns:
      plate_name  : str  e.g. "CA-Amateur Radio Call Letters-Block"
      series_name : str  e.g. "CA01-Script-2001" or ""
    """
    # Remove surrounding whitespace and split on " - "
    parts = [p.strip() for p in description.split(' - ')]

    # parts[0] is always the state full name — skip it
    if len(parts) < 2:
        return description.strip(), ''

    core_name = parts[1]   # Required: the plate type/title
    variant   = parts[2] if len(parts) > 2 else ''

    # Reconstruct plate_number in your convention: STATE-Name-Variant
    if variant:
        plate_number = f"{state_code}-{core_name}-{variant}"
    else:
        plate_number = f"{state_code}-{core_name}"

    # Series lookup for CA
    series_name = ''
    if state_code.upper() == 'CA':
        variant_key = variant.lower().strip()
        if variant_key in CA_SERIES_MAP:
            series_name = CA_SERIES_MAP[variant_key]
        else:
            # Specialty plates, government plates, etc. — use the catch-all CA specialty series
            series_name = CA_SPECIALTY_SERIES

    return plate_number, series_name


def download_image(url, dest_path, retries=2, delay=0.5):
    """Download url to dest_path. Returns True on success."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; PlateConverter/1.0)',
        'Accept': 'image/*,*/*',
    }
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=15) as response:
                content = response.read()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(content)
            return True
        except (URLError, HTTPError, OSError) as e:
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
            else:
                return False
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Convert Keegan/DMV-sourced CSV to plates_react bulk import format.'
    )
    parser.add_argument('input_csv',  help='Input CSV file (State|Description|Plate Image|Source)')
    parser.add_argument('output_csv', help='Output CSV file for bulk import')
    parser.add_argument(
        '--download-images', metavar='DIR',
        help='Download plate images into DIR/STATE/ subdirectories'
    )
    parser.add_argument(
        '--state', metavar='XX',
        help='Filter to a single state code (e.g. CA, MD, TX)'
    )
    parser.add_argument(
        '--delay', type=float, default=0.3,
        help='Seconds between image download requests (default: 0.3)'
    )
    args = parser.parse_args()

    state_filter = args.state.upper() if args.state else None
    download_dir = Path(args.download_images) if args.download_images else None

    output_columns = [
        'plate_number', 'region_name', 'category_name', 'series_name',
        'description', 'year_introduced', 'year_discontinued', 'is_active',
        'plate_header', 'plate_base', 'plate_serial', 'plate_footer',
        'image_url', 'image_filename',
    ]

    # ── Counters ──────────────────────────────────────────────────────────────
    total_read   = 0
    total_out    = 0
    skipped      = 0
    dl_ok        = 0
    dl_fail      = 0
    unknown_cats = []   # rows that defaulted to Standard
    missing_states = set()

    print(f"Reading: {args.input_csv}")
    if state_filter:
        print(f"Filtering to state: {state_filter}")
    if download_dir:
        print(f"Downloading images to: {download_dir}")

    with open(args.input_csv, newline='', encoding='utf-8-sig') as fin, \
         open(args.output_csv, 'w', newline='', encoding='utf-8') as fout:

        reader  = csv.DictReader(fin)
        writer  = csv.DictWriter(fout, fieldnames=output_columns)
        writer.writeheader()

        # Normalise header lookup (case-insensitive)
        fieldnames_lower = {k.lower().strip(): k for k in (reader.fieldnames or [])}

        def get_col(row, *candidates):
            for c in candidates:
                actual = fieldnames_lower.get(c.lower())
                if actual and actual in row:
                    return (row[actual] or '').strip()
            return ''

        for row in reader:
            total_read += 1

            state_code  = get_col(row, 'State', 'state').upper()
            description = get_col(row, 'Description', 'description')
            image_cell  = get_col(row, 'Plate Image', 'plate image', 'image')

            if state_filter and state_code != state_filter:
                skipped += 1
                continue

            if not state_code or not description:
                skipped += 1
                continue

            region_name = STATE_CODE_TO_REGION.get(state_code, '')
            if not region_name:
                missing_states.add(state_code)
                region_name = state_code  # leave as-is, user can fix

            plate_number, series_name = parse_description(state_code, description)
            category_name = infer_category(description)

            if category_name == DEFAULT_CATEGORY:
                unknown_cats.append(plate_number)

            image_url      = extract_image_url(image_cell)
            image_filename = ''

            if image_url and download_dir:
                slug           = plate_number.replace(' ', '-')
                image_filename = url_to_safe_filename(image_url, state_code, slug)
                dest_path      = download_dir / state_code.lower() / image_filename

                if dest_path.exists():
                    dl_ok += 1
                    print(f"  [skip] already exists: {image_filename}")
                else:
                    ok = download_image(image_url, dest_path)
                    if ok:
                        dl_ok += 1
                        print(f"  [ok]   {image_filename}")
                    else:
                        dl_fail += 1
                        print(f"  [FAIL] {image_url}")

                time.sleep(args.delay)

            elif image_url:
                # Store URL and suggested local filename but don't download
                slug           = plate_number.replace(' ', '-')
                image_filename = url_to_safe_filename(image_url, state_code, slug)

            writer.writerow({
                'plate_number':       plate_number,
                'region_name':        region_name,
                'category_name':      category_name,
                'series_name':        series_name,
                'description':        '',          # blank — fill in yourself or with AI
                'year_introduced':    '',          # blank — fill with AI
                'year_discontinued':  '',          # blank — fill with AI
                'is_active':          '1',
                'plate_header':       '',          # blank — fill as needed
                'plate_base':         '',
                'plate_serial':       '',
                'plate_footer':       '',
                'image_url':          image_url,
                'image_filename':     image_filename,
            })
            total_out += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print(f"  Input rows read    : {total_read}")
    print(f"  Output rows written: {total_out}")
    print(f"  Skipped (filtered) : {skipped}")
    if download_dir:
        print(f"  Images downloaded  : {dl_ok}")
        print(f"  Download failures  : {dl_fail}")
    print("=" * 55)

    if missing_states:
        print(f"\n  WARNING — Unknown state codes (region left blank): {sorted(missing_states)}")
        print("  Add these to STATE_CODE_TO_REGION at the top of this script.")

    defaulted = len(unknown_cats)
    if defaulted:
        print(f"\n  NOTE — {defaulted} row(s) defaulted to category 'Standard'.")
        print("  Review and update category_name for:")
        for name in unknown_cats[:10]:
            print(f"    {name}")
        if defaulted > 10:
            print(f"    ... and {defaulted - 10} more")

    print(f"\nOutput written to: {args.output_csv}")
    print("Next step: open output CSV, fill years + descriptions, then import via Admin > Library > CSV Bulk Import.")


if __name__ == '__main__':
    main()
