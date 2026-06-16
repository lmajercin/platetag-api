#!/usr/bin/env python3
"""
wiki_plates_scraper.py
======================
Scrapes a Wikipedia vehicle registration plates page and outputs a CSV
ready for review / import into the platetag-api database.

OUTPUT CSV columns (flat — one row per plate):
  country_code, region_code, series_name, series_year_start, series_year_end,
  series_header, series_footer, series_background, series_notes,
  plate_name, plate_vehicle_class, plate_category, plate_serial_format,
  plate_detail, plate_image_filename

Usage:
  python wiki_plates_scraper.py --state CA
  python wiki_plates_scraper.py --url "https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Pennsylvania"
  python wiki_plates_scraper.py --state CA --sections passenger specialty
  python wiki_plates_scraper.py --state CA --output ca_series_plates.csv

SECTION filters:
  passenger   - Passenger baseplates (1963-present only, skips pre-1963 history)
  specialty   - Optional/specialty plates
  nonpassenger - Non-passenger vehicle plates (commercial, motorcycle, trailer, etc.)
  all         - All sections (default)

Notes:
  - Pre-1963 historical plates are skipped by default (too old, no collector images)
  - Images are NOT available from Wikipedia; image_filename is left blank
  - Series naming: "{STATE}-{VehicleClass}-{Year}" e.g. "CA-Passenger-1963"
  - Specialty plates get their own series per type: "CA-Specialty-WhiteTail"
  - This script produces a CSV for human review before DB import
  - Run the companion import command after reviewing: php artisan plates:import <csv>
"""

import argparse
import csv
import re
import sys
from io import StringIO
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("ERROR: Install beautifulsoup4 first: pip install requests beautifulsoup4")

# ── State → Wikipedia URL map ─────────────────────────────────────────────────
WIKI_URL_MAP = {
    'AL': 'Vehicle_registration_plates_of_Alabama',
    'AK': 'Vehicle_registration_plates_of_Alaska',
    'AZ': 'Vehicle_registration_plates_of_Arizona',
    'AR': 'Vehicle_registration_plates_of_Arkansas',
    'CA': 'Vehicle_registration_plates_of_California',
    'CO': 'Vehicle_registration_plates_of_Colorado',
    'CT': 'Vehicle_registration_plates_of_Connecticut',
    'DE': 'Vehicle_registration_plates_of_Delaware',
    'DC': 'Vehicle_registration_plates_of_the_District_of_Columbia',
    'FL': 'Vehicle_registration_plates_of_Florida',
    'GA': 'Vehicle_registration_plates_of_Georgia_(U.S._state)',
    'HI': 'Vehicle_registration_plates_of_Hawaii',
    'ID': 'Vehicle_registration_plates_of_Idaho',
    'IL': 'Vehicle_registration_plates_of_Illinois',
    'IN': 'Vehicle_registration_plates_of_Indiana',
    'IA': 'Vehicle_registration_plates_of_Iowa',
    'KS': 'Vehicle_registration_plates_of_Kansas',
    'KY': 'Vehicle_registration_plates_of_Kentucky',
    'LA': 'Vehicle_registration_plates_of_Louisiana',
    'ME': 'Vehicle_registration_plates_of_Maine',
    'MD': 'Vehicle_registration_plates_of_Maryland',
    'MA': 'Vehicle_registration_plates_of_Massachusetts',
    'MI': 'Vehicle_registration_plates_of_Michigan',
    'MN': 'Vehicle_registration_plates_of_Minnesota',
    'MS': 'Vehicle_registration_plates_of_Mississippi',
    'MO': 'Vehicle_registration_plates_of_Missouri',
    'MT': 'Vehicle_registration_plates_of_Montana',
    'NE': 'Vehicle_registration_plates_of_Nebraska',
    'NV': 'Vehicle_registration_plates_of_Nevada',
    'NH': 'Vehicle_registration_plates_of_New_Hampshire',
    'NJ': 'Vehicle_registration_plates_of_New_Jersey',
    'NM': 'Vehicle_registration_plates_of_New_Mexico',
    'NY': 'Vehicle_registration_plates_of_New_York',
    'NC': 'Vehicle_registration_plates_of_North_Carolina',
    'ND': 'Vehicle_registration_plates_of_North_Dakota',
    'OH': 'Vehicle_registration_plates_of_Ohio',
    'OK': 'Vehicle_registration_plates_of_Oklahoma',
    'OR': 'Vehicle_registration_plates_of_Oregon',
    'PA': 'Vehicle_registration_plates_of_Pennsylvania',
    'RI': 'Vehicle_registration_plates_of_Rhode_Island',
    'SC': 'Vehicle_registration_plates_of_South_Carolina',
    'SD': 'Vehicle_registration_plates_of_South_Dakota',
    'TN': 'Vehicle_registration_plates_of_Tennessee',
    'TX': 'Vehicle_registration_plates_of_Texas',
    'UT': 'Vehicle_registration_plates_of_Utah',
    'VT': 'Vehicle_registration_plates_of_Vermont',
    'VA': 'Vehicle_registration_plates_of_Virginia',
    'WA': 'Vehicle_registration_plates_of_Washington_(state)',
    'WV': 'Vehicle_registration_plates_of_West_Virginia',
    'WI': 'Vehicle_registration_plates_of_Wisconsin',
    'WY': 'Vehicle_registration_plates_of_Wyoming',
    # Canadian provinces
    'AB': 'Vehicle_registration_plates_of_Alberta',
    'BC': 'Vehicle_registration_plates_of_British_Columbia',
    'MB': 'Vehicle_registration_plates_of_Manitoba',
    'NB': 'Vehicle_registration_plates_of_New_Brunswick',
    'NL': 'Vehicle_registration_plates_of_Newfoundland_and_Labrador',
    'NS': 'Vehicle_registration_plates_of_Nova_Scotia',
    'ON': 'Vehicle_registration_plates_of_Ontario',
    'PE': 'Vehicle_registration_plates_of_Prince_Edward_Island',
    'QC': 'Vehicle_registration_plates_of_Quebec',
    'SK': 'Vehicle_registration_plates_of_Saskatchewan',
}

# ── State → country code ──────────────────────────────────────────────────────
US_STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
CA_PROVINCES = set('AB BC MB NB NL NS ON PE QC SK'.split())

# ── Category inference map ────────────────────────────────────────────────────
# Maps keywords found in plate type/section to our DB category names.
CATEGORY_MAP = [
    # (keyword_in_type_or_section, category_name)
    (['veteran', 'military', 'disabled veteran', 'pearl harbor', 'medal of honor',
      'gold star', 'pow', 'purple heart', 'legion of valor', 'we will never forget'],
     'Military / Veteran'),
    (['disabled person', 'disabled', 'accessibility'],
     'Disabled / Accessibility'),
    (['school', 'university', 'college', 'ucla', 'usc'],
     'School'),
    (['dealer', 'manufacturer', 'dismantler', 'distributor', 'transporter', 'remanufacturer'],
     'Dealer / Manufacturer'),
    (['exempt', 'government', 'legislative', 'assembly', 'senator', 'congress',
      'public service', 'honorary consul', 'foreign organization'],
     'Government / Exempt'),
    (['firefighter', 'fire', 'first responder'],
     'First Responder'),
    (['whale tail', 'coast', 'ocean', 'lake tahoe', 'yosemite', 'protect',
      'environmental', 'conservation', 'agriculture'],
     'Conservation / Environment'),
    (['breast cancer', 'health', 'awareness', 'spay', 'neuter'],
     'Health & Awareness'),
    (['sport', 'olympic', 'tournament of roses', 'baseball', '49ers', 'raiders',
      'lakers', 'athletic'],
     'Sports Team / Sporting Activities'),
    (['arts', 'art council', 'museum', 'culture', 'snoopy', 'peanuts'],
     'Arts / Culture'),
    (['agricultural', 'farm'],
     'Agricultural'),
    (['fraternal', 'civic', 'bill of rights', 'bicentennial'],
     'Fraternal / Civic'),
    (['historical', 'antique', 'horseless carriage', 'year-of-manufacture',
      'legacy', 'sesquicentennial', 'commemorative'],
     'Historical / Commemorative'),
]

DEFAULT_CATEGORY = 'Standard Issue'


def infer_category(type_text: str, section_text: str) -> str:
    combined = (type_text + ' ' + section_text).lower()
    for keywords, category in CATEGORY_MAP:
        if any(kw in combined for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def infer_vehicle_class(type_text: str) -> str:
    t = type_text.lower()
    if 'motorcycle' in t:
        return 'Motorcycle'
    if 'trailer' in t:
        return 'Trailer'
    if 'commercial' in t or 'apportioned' in t or 'tractor' in t:
        return 'Commercial'
    if 'moped' in t:
        return 'Motorcycle'
    return 'Passenger'


def clean_text(s: str) -> str:
    """Strip Wikipedia citation markers and extra whitespace."""
    s = re.sub(r'\[\d+\]', '', s)   # [1], [24], etc.
    s = s.replace('\xa0', ' ')      # non-breaking space
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def expand_table(table) -> list[list[str]]:
    """
    Expand a wikitable, properly handling rowspan and colspan.
    Returns a 2D list of strings (including the header row).
    """
    grid = []
    rowspan_map = {}  # col_index → (remaining_rows, value)

    for tr in table.find_all('tr'):
        row = []
        cells = tr.find_all(['td', 'th'])
        cell_iter = iter(cells)
        col = 0

        # How many logical columns are in this row?
        # We need to place cells accounting for pending rowspans
        placed = {}  # col_index → value from a rowspan

        # Resolve any pending rowspans for this row
        for ci, (rem, val) in list(rowspan_map.items()):
            placed[ci] = val
            if rem <= 1:
                del rowspan_map[ci]
            else:
                rowspan_map[ci] = (rem - 1, val)

        logical_col = 0
        for cell in cells:
            # Advance logical_col past any rowspan-filled positions
            while logical_col in placed:
                logical_col += 1

            text = clean_text(cell.get_text())
            rowspan = int(cell.get('rowspan', 1))
            colspan = int(cell.get('colspan', 1))

            for c in range(colspan):
                placed[logical_col + c] = text
                if rowspan > 1:
                    rowspan_map[logical_col + c] = (rowspan - 1, text)
            logical_col += colspan

        # Fill in all columns in order
        max_col = max(placed.keys()) + 1 if placed else 0
        row = [placed.get(c, '') for c in range(max_col)]
        if row:
            grid.append(row)

    return grid


def year_from_text(text: str) -> str:
    """Extract first 4-digit year from text."""
    m = re.search(r'\b(1[89]\d\d|20[012]\d)\b', text)
    return m.group(1) if m else ''


def slug_from(text: str) -> str:
    """Simple slug: lowercase, spaces → hyphens, strip non-alphanum-hyphen."""
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9\- ]+', '', s)
    s = re.sub(r'[\s\-]+', '-', s)
    return s.strip('-')


def fetch_wiki_page(url: str) -> str:
    req = Request(url, headers={'User-Agent': 'PlateTagBot/1.0 (educational use)'})
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except URLError as e:
        sys.exit(f"ERROR fetching {url}: {e}")


def _get_section_for_table(table) -> str:
    """Return the nearest preceding heading text for a table."""
    prev = table.find_previous(['h2', 'h3', 'h4'])
    return clean_text(prev.get_text()) if prev else ''


def parse_passenger_tables(soup, state_code: str, region_name: str,
                            country_code: str, skip_pre1963: bool = True) -> list[dict]:
    rows = []
    for table in soup.find_all('table', class_=lambda c: c and 'wikitable' in c):
        section = _get_section_for_table(table).lower()
        # Include 1963-present; skip pre-1963 historical sections
        if 'pre-state' in section or '1914' in section or '1962' in section:
            continue
        if ('1963' in section or 'present' in section
                or 'passenger baseplate' in section or 'baseplate' in section):
            rows.extend(_parse_generic_plate_table(
                table, state_code, region_name, country_code,
                section_label='Passenger', skip_pre1963=skip_pre1963,
            ))
    return rows


def _build_series_name(state_code: str, vehicle_class: str, year: str,
                       slogan: str = '', type_name: str = '') -> str:
    """
    Build a series slug following the convention: STATE-VehicleClass-Year[-Variant]
    e.g. CA-Passenger-1963, CA-Passenger-1982-Golden-State
    """
    parts = [state_code, vehicle_class.replace(' ', '-'), year]
    if slogan and slogan.lower() != 'none':
        variant = re.sub(r'[^a-zA-Z0-9 ]', '', slogan)[:30].strip()
        variant = re.sub(r'\s+', '-', variant)
        if variant:
            parts.append(variant)
    elif type_name:
        variant = re.sub(r'[^a-zA-Z0-9 ]', '', type_name)[:30].strip()
        variant = re.sub(r'\s+', '-', variant)
        if variant:
            parts.append(variant)
    return '-'.join(p for p in parts if p)


def _parse_generic_plate_table(table, state_code: str, region_name: str,
                                 country_code: str, section_label: str,
                                 default_vehicle_class: str = 'Passenger',
                                 skip_pre1963: bool = True) -> list[dict]:
    """
    Parse any Wikipedia plate table with flexible column detection.
    Handles rowspan/colspan merging via expand_table().
    Returns list of row dicts matching our CSV schema.
    """
    rows_out = []
    grid = expand_table(table)
    if len(grid) < 2:
        return rows_out

    # Header row — lowercased for matching
    headers = [h.lower() for h in grid[0]]

    def col_idx(keywords):
        """Return index of first header containing any keyword."""
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    ci_image  = col_idx(['image'])
    ci_year   = col_idx(['first issued', 'dates issued', 'date issued'])
    ci_design = col_idx(['design'])
    ci_slogan = col_idx(['slogan'])
    ci_serial = col_idx(['serial format'])
    ci_serials= col_idx(['serials issued'])
    ci_notes  = col_idx(['notes'])
    ci_type   = col_idx(['type'])

    def gcell(row_cells, idx, default=''):
        if idx is None or idx >= len(row_cells):
            return default
        return row_cells[idx].strip()

    seen_series = set()  # avoid exact duplicate rows from rowspan expansion

    for data_row in grid[1:]:
        year_text   = gcell(data_row, ci_year)
        design_text = gcell(data_row, ci_design)
        slogan_text = gcell(data_row, ci_slogan)
        serial_text = gcell(data_row, ci_serial)
        notes_text  = gcell(data_row, ci_notes)
        type_text   = gcell(data_row, ci_type)

        year = year_from_text(year_text)

        # Skip pre-1963 rows if requested
        if skip_pre1963 and year and int(year) < 1963:
            continue
        # Skip rows with no useful data
        if not year and not type_text and not design_text and not serial_text:
            continue
        # Skip "Stickers" section rows (no plate, just a sticker)
        if section_label == 'Stickers':
            continue

        plate_type = type_text if type_text else section_label
        vehicle_class = infer_vehicle_class(plate_type + ' ' + design_text)
        category = infer_category(plate_type, section_label)

        series_name = _build_series_name(
            state_code=state_code,
            vehicle_class=vehicle_class,
            year=year,
            slogan=slogan_text,
            type_name=plate_type if plate_type not in (section_label, 'Passenger') else '',
        )

        # Deduplicate: rowspan expansion can produce identical rows
        dedup_key = (series_name, plate_type, year)
        if dedup_key in seen_series:
            continue
        seen_series.add(dedup_key)

        # Plate name
        if slogan_text and slogan_text.lower() not in ('none', ''):
            plate_name = f"{region_name} {slogan_text}"
        elif type_text and type_text not in (section_label, ''):
            plate_name = f"{region_name} {type_text}"
        else:
            plate_name = (f"{region_name} {vehicle_class} {year}".strip()
                          if year else f"{region_name} {section_label}")

        row = {
            'country_code':        country_code,
            'region_code':         state_code,
            'region_name':         region_name,
            'series_name':         series_name,
            'series_year_start':   year,
            'series_year_end':     '',
            'series_header':       region_name,
            'series_footer':       slogan_text if slogan_text.lower() not in ('none', '') else '',
            'series_background':   design_text,
            'series_notes':        notes_text,
            'plate_name':          plate_name,
            'plate_vehicle_class': vehicle_class,
            'plate_category':      category,
            'plate_serial_format': serial_text,
            'plate_detail':        notes_text,
            'plate_image_filename': '',
        }
        rows_out.append(row)

    return rows_out


def parse_specialty_tables(soup, state_code: str, region_name: str,
                            country_code: str) -> list[dict]:
    rows = []
    for table in soup.find_all('table', class_=lambda c: c and 'wikitable' in c):
        section = _get_section_for_table(table).lower()
        if 'optional' in section or 'specialty' in section:
            rows.extend(_parse_generic_plate_table(
                table, state_code, region_name, country_code,
                section_label='Specialty', skip_pre1963=False,
            ))
    return rows


def parse_nonpassenger_tables(soup, state_code: str, region_name: str,
                               country_code: str) -> list[dict]:
    rows = []
    for table in soup.find_all('table', class_=lambda c: c and 'wikitable' in c):
        section = _get_section_for_table(table).lower()
        if ('non-passenger' in section or 'occupational' in section
                or 'legislative' in section):
            rows.extend(_parse_generic_plate_table(
                table, state_code, region_name, country_code,
                section_label='Non-Passenger', skip_pre1963=False,
            ))
    return rows


CSV_FIELDNAMES = [
    'country_code', 'region_code', 'region_name',
    'series_name', 'series_year_start', 'series_year_end',
    'series_header', 'series_footer', 'series_background', 'series_notes',
    'plate_name', 'plate_vehicle_class', 'plate_category',
    'plate_serial_format', 'plate_detail', 'plate_image_filename',
]


def write_csv(rows: list[dict], output_path: str):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in CSV_FIELDNAMES})
    print(f"Written {len(rows)} rows → {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Scrape Wikipedia plate data to CSV')
    parser.add_argument('--state', help='Two-letter state/province code (e.g. CA, PA, ON)')
    parser.add_argument('--url',   help='Explicit Wikipedia URL to scrape')
    parser.add_argument('--sections', nargs='+',
                        choices=['passenger', 'specialty', 'nonpassenger', 'all'],
                        default=['all'],
                        help='Table sections to include (default: all)')
    parser.add_argument('--output', help='Output CSV filename (default: {state}_wiki.csv)')
    parser.add_argument('--include-pre1963', action='store_true',
                        help='Include historical pre-1963 plates (CA only; very long)')
    args = parser.parse_args()

    if not args.state and not args.url:
        parser.error('Provide --state CODE or --url URL')

    # Resolve URL
    if args.url:
        url = args.url
        # Try to extract state code from URL
        m = re.search(r'_of_([A-Z][a-z]+(?:_[A-Z][a-z]+)*)', url)
        state_code = m.group(1)[:2].upper() if m else 'XX'
    else:
        state_code = args.state.upper()
        slug = WIKI_URL_MAP.get(state_code)
        if not slug:
            sys.exit(f"No Wikipedia URL mapping for '{state_code}'. Use --url instead.")
        url = f"https://en.wikipedia.org/wiki/{slug}"

    country_code = 'US' if state_code in US_STATES else ('CA' if state_code in CA_PROVINCES else 'US')

    # Region name = state abbreviation (DB lookup will be by region_code)
    # We output region_code and let the importer map to region_id
    # For display, use a friendly name
    STATE_NAMES = {
        'CA': 'California', 'PA': 'Pennsylvania', 'HI': 'Hawaii',
        'NY': 'New York', 'TX': 'Texas', 'FL': 'Florida',
        'IL': 'Illinois', 'OH': 'Ohio', 'GA': 'Georgia',
        'NC': 'North Carolina', 'MI': 'Michigan', 'NJ': 'New Jersey',
        'VA': 'Virginia', 'WA': 'Washington', 'AZ': 'Arizona',
        'MA': 'Massachusetts', 'TN': 'Tennessee', 'IN': 'Indiana',
        'MO': 'Missouri', 'MD': 'Maryland', 'WI': 'Wisconsin',
        'CO': 'Colorado', 'MN': 'Minnesota', 'SC': 'South Carolina',
        'AL': 'Alabama', 'LA': 'Louisiana', 'KY': 'Kentucky',
        'OR': 'Oregon', 'OK': 'Oklahoma', 'CT': 'Connecticut',
        'UT': 'Utah', 'IA': 'Iowa', 'NV': 'Nevada',
        'AR': 'Arkansas', 'MS': 'Mississippi', 'KS': 'Kansas',
        'NM': 'New Mexico', 'NE': 'Nebraska', 'WV': 'West Virginia',
        'ID': 'Idaho', 'HI': 'Hawaii', 'NH': 'New Hampshire',
        'ME': 'Maine', 'MT': 'Montana', 'RI': 'Rhode Island',
        'DE': 'Delaware', 'SD': 'South Dakota', 'ND': 'North Dakota',
        'AK': 'Alaska', 'VT': 'Vermont', 'WY': 'Wyoming',
        'DC': 'District of Columbia',
        'AB': 'Alberta', 'BC': 'British Columbia', 'MB': 'Manitoba',
        'NB': 'New Brunswick', 'NL': 'Newfoundland and Labrador',
        'NS': 'Nova Scotia', 'ON': 'Ontario', 'PE': 'Prince Edward Island',
        'QC': 'Quebec', 'SK': 'Saskatchewan',
    }
    region_name = STATE_NAMES.get(state_code, state_code)

    output_path = args.output or f"{state_code.lower()}_wiki.csv"

    sections = args.sections
    if 'all' in sections:
        sections = ['passenger', 'specialty', 'nonpassenger']

    skip_pre1963 = not args.include_pre1963

    print(f"Fetching {url} ...")
    html = fetch_wiki_page(url)
    soup = BeautifulSoup(html, 'html.parser')

    all_rows = []

    if 'passenger' in sections:
        print("Parsing passenger baseplate tables ...")
        prows = parse_passenger_tables(soup, state_code, region_name, country_code, skip_pre1963)
        print(f"  → {len(prows)} passenger rows")
        all_rows.extend(prows)

    if 'specialty' in sections:
        print("Parsing specialty plate tables ...")
        srows = parse_specialty_tables(soup, state_code, region_name, country_code)
        print(f"  → {len(srows)} specialty rows")
        all_rows.extend(srows)

    if 'nonpassenger' in sections:
        print("Parsing non-passenger plate tables ...")
        nrows = parse_nonpassenger_tables(soup, state_code, region_name, country_code)
        print(f"  → {len(nrows)} non-passenger rows")
        all_rows.extend(nrows)

    if not all_rows:
        print("WARNING: No rows extracted. The Wikipedia page structure may differ from expected.")
        print("  Try inspecting the page manually and using --sections to narrow scope.")
        sys.exit(1)

    write_csv(all_rows, output_path)
    print()
    print("Next steps:")
    print(f"  1. Open {output_path} and review/clean the data")
    print("  2. Adjust series_name values to follow your naming convention")
    print("  3. Fill in plate_image_filename once you have images")
    print("  4. Run: php artisan plates:import-csv {output_path}")


if __name__ == '__main__':
    main()
