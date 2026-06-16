#!/usr/bin/env python3
r"""
import_specialty_plates.py
==========================
Import specialty plates from an image folder directly into the DB.
Generates plate name + slug from filename, assigns category by keyword,
links to a given series_id. Skips plates whose slug already exists.

Usage:
  python tools/import_specialty_plates.py --folder "P:\Larry Doc\Plates\assets\images\co\CO-Specialty" --series-id 620 --state co --dry-run
  python tools/import_specialty_plates.py --folder "P:\Larry Doc\Plates\assets\images\co\CO-Specialty" --series-id 620 --state co --apply

  python tools/import_specialty_plates.py --folder "P:\Larry Doc\Plates\assets\images\pa\2017-VisitPA-Series\2017-visit-pa-specialty" --series-id 633 --state pa --apply
  python tools/import_specialty_plates.py --folder "P:\Larry Doc\Plates\assets\images\pa\2025-let-freedom-ring\2025-let-freedom-ring-specialty" --series-id 632 --state pa --apply
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

MYSQL   = Path(r'C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe')
DB_USER = 'root'
DB_PASS = r'4rfv$RFV'
DB_NAME = 'platetag_api'

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# Category IDs (from your DB - adjust if needed)
# 1=General/Specialty, 2=Education, 3=Military/Veteran, 4=Dealer,
# 5=Disabled, 6=Government, 7=Emergency/First Responder, 8=Conservation,
# 9=Health/Medical, 10=Sports, 12=Agriculture, 14=Historic/Antique
CATEGORY_KEYWORDS = {
    3: [  # Military / Veteran
        'veteran', 'fallen', 'medal-of-honor', 'medal_of_honor', 'purple-heart', 'purple_heart',
        'bronze-star', 'bronze_star', 'silver-star', 'silver_star', 'navy-cross', 'navy_cross',
        'air-force-cross', 'air_force_cross', 'service-cross', 'service_cross',
        'flying-cross', 'distinguished', 'combat', 'pearl-harbor', 'pearl_harbor',
        'prisoner-of-war', 'pow', 'gold-star', 'gold_star',
        'air-force', 'army', 'navy', 'marine', 'coast-guard', 'coast_guard',
        'national-guard', 'airborne', 'infantry', 'submarine', 'udt-seal', 'expeditionary',
        'military', 'armed-forces', 'armed_forces', 'civil-air-patrol', 'civil_air_patrol',
        'korean-war', 'vietnam', 'afghanistan', 'iraq', 'operation-desert', 'world-war',
        'space-force', 'legion-of-valor', 'congressional-gold', 'borinqueneers',
        'combat-action', 'air_patrol', '82_airborne', '82nd-airborne',
    ],
    2: [  # Education
        'university', 'college', 'school-of-mines', 'academic', 'student',
        'alumni', 'education', 'homeschool', 'academic',
    ],
    7: [  # Emergency / First Responder
        'firefighter', 'fire-company', 'fire-co', 'fire-dept', 'fire-department',
        'fire_co', 'ems', 'emergency-medical', 'emergency_medical',
        'paramedic', 'ambulance', 'rescue', 'first-responder', 'first_responder',
        'hose-company', 'hose_company', 'fire-company', 'fire_company',
        'fallen-public-safety', 'firefighter', 'fire', 'vol-fire', 'vfd',
        'police', 'state-patrol',
    ],
    5: [  # Disabled Person
        'disabled', 'handicapped', 'wheelchair', 'hearing-impaired',
    ],
    6: [  # Government
        'government', 'representative', 'senator', 'congress', 'house-of-rep',
        'state-rep', 'state-sen', 'governor', 'secretary', 'legislative',
    ],
    8: [  # Conservation / Environment
        'conservation', 'wildlife', 'environment', 'nature', 'forestry',
        'state-park', 'state_park', 'national-park', 'national_park',
        'river', 'ocean', 'pollinator', 'whale', 'salmon', 'raptor',
        'greyhound', 'shelter-pet', 'share-the-road', 'support-the-horse',
        'waterfowl', 'equine',
    ],
    9: [  # Health / Medical
        'cancer', 'diabetes', 'epilepsy', 'als', 'down-syndrome', 'child-loss',
        'childhood-cancer', 'breast-cancer', 'autism', 'chop', 'hospice',
        'donate-life', 'medical', 'craig-hospital', 'flight-for-life',
    ],
    10: [  # Sports
        'broncos', 'nuggets', 'avalanche', 'rockies', 'trail-blazers',
        'trail_blazers', 'ducks', 'beavers', 'pikes-peak', 'ski-country',
        'special-olympics',
    ],
    12: [  # Agriculture / Farm
        'farm', 'agriculture', 'ranch', 'husbandry', 'livestock',
    ],
    14: [  # Historic / Antique
        'antique', 'historic', 'horseless-carriage', 'classic', 'collectible',
        'collector', 'old-timer', 'street-rod',
    ],
}

DEFAULT_CATEGORY = 1  # General / Specialty


def run_sql(sql: str) -> list[dict]:
    cmd = [str(MYSQL), f'-u{DB_USER}', f'-p{DB_PASS}', '--batch', '--column-names', DB_NAME, '-e', sql]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = '\n'.join(l for l in result.stderr.splitlines() if 'insecure' not in l.lower())
    if result.returncode != 0 and stderr:
        print(f"[SQL ERR] {stderr}", file=sys.stderr)
        return []
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    if not lines:
        return []
    headers = lines[0].split('\t')
    return [dict(zip(headers, line.split('\t'))) for line in lines[1:]]


def run_sql_exec(sql: str) -> bool:
    cmd = [str(MYSQL), f'-u{DB_USER}', f'-p{DB_PASS}', '--batch', DB_NAME, '-e', sql]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = '\n'.join(l for l in result.stderr.splitlines() if 'insecure' not in l.lower())
    if result.returncode != 0 and stderr:
        print(f"  [WARN] {stderr}", file=sys.stderr)
        return False
    return True


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


ABBREV_MAP = {
    r'\bPwd\b': 'PWD',
    r'\bAls\b': 'ALS',
    r'\bEms\b': 'EMS',
    r'\bPow\b': 'POW',
    r'\bAf\b':  'AF',
    r'\bDvm\b': 'DVM',
    r'\bMd\b':  'MD',
}


def fix_title_case(s: str) -> str:
    """Title-case but preserve ordinals (4th, 3rd) and known abbreviations."""
    # Basic title case
    s = s.title()
    # Fix ordinals: 1St → 1st, 2Nd → 2nd, 3Rd → 3rd, 4Th → 4th, 5Th → 5th
    s = re.sub(r'(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), s)
    # Fix abbreviations
    for pattern, replacement in ABBREV_MAP.items():
        s = re.sub(pattern, replacement, s)
    return s


def filename_to_name(stem: str, state_code: str) -> str:
    """Convert a filename stem like 'co-air-force-cross' to 'Air Force Cross'."""
    # Strip leading state code prefix
    name = re.sub(rf'^{re.escape(state_code.lower())}-', '', stem, flags=re.IGNORECASE)
    # Replace delimiters with space
    name = re.sub(r'[-_]+', ' ', name)
    # Strip parenthetical duplicate markers: (2), (3), etc. — must come FIRST
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    # Strip trailing year tags like 2025
    name = re.sub(r'\s+\d{4}$', '', name)
    # Strip PA DMV suffixes
    name = re.sub(r'\s+registration\s+plate\s*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+sample\s+plate\s*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+plate\s+[a-z]\s*$', '', name, flags=re.IGNORECASE)
    # Title case with fixes
    return fix_title_case(name.strip())


def assign_category(filename_lower: str) -> int:
    """Match keywords against hyphen/underscore-delimited tokens in the filename."""
    # Split filename into tokens for word-boundary matching
    tokens = re.split(r'[-_]', filename_lower)
    joined_hyphen = '-' + '-'.join(tokens) + '-'   # e.g. -ca-pow-ex-prisoner-
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            # Normalize keyword to hyphens and wrap with delimiters
            kw_norm = '-' + kw.replace('_', '-') + '-'
            if kw_norm in joined_hyphen:
                return cat_id
    return DEFAULT_CATEGORY


def get_state_full_name(state_code: str) -> str:
    names = {
        'co': 'Colorado', 'ca': 'California', 'pa': 'Pennsylvania',
        'or': 'Oregon', 'fl': 'Florida', 'ny': 'New York',
        'tn': 'Tennessee', 'hi': 'Hawaii',
    }
    return names.get(state_code.lower(), state_code.upper())


def main():
    parser = argparse.ArgumentParser(description='Import specialty plates from an image folder')
    parser.add_argument('--folder', required=True, help='Path to folder of specialty plate images')
    parser.add_argument('--series-id', required=True, type=int, help='DB series_id to assign plates to')
    parser.add_argument('--state', required=True, help='Two-letter state code')
    parser.add_argument('--skip-unprefixed', action='store_true',
                        help='Skip image files whose name does not start with the state code prefix')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing to DB')
    parser.add_argument('--apply', action='store_true', help='Write to DB')
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        sys.exit('Specify --dry-run or --apply')

    folder = Path(args.folder)
    if not folder.exists():
        sys.exit(f'Folder not found: {folder}')

    state = args.state.lower()
    state_full = get_state_full_name(state)

    # Load existing slugs AND image filenames to avoid duplicates
    existing = run_sql("SELECT slug, image_filename FROM plates")
    existing_slugs = {r['slug'] for r in existing}
    existing_images = {r['image_filename'] for r in existing if r.get('image_filename')}

    # Scan images
    prefix = state.lower() + '-'
    images = sorted(f for f in folder.iterdir()
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTS
                    and (not args.skip_unprefixed or f.name.lower().startswith(prefix)))
    print(f"Images found      : {len(images)}")
    print(f"Existing DB slugs : {len(existing_slugs)}")
    print()

    to_insert = []
    skipped_exists = 0

    for img in images:
        stem = img.stem
        short_name = filename_to_name(stem, state)
        # Only prepend state full name if not already present
        if short_name.lower().startswith(state_full.lower()):
            display_name = short_name
        else:
            display_name = f"{state_full} {short_name}"

        slug = slugify(display_name)

        if slug in existing_slugs or img.name in existing_images:
            skipped_exists += 1
            continue

        cat_id = assign_category(stem.lower())
        to_insert.append({
            'name': display_name,
            'slug': slug,
            'filename': img.name,
            'category_id': cat_id,
        })

    print(f"Already in DB     : {skipped_exists}")
    print(f"New plates        : {len(to_insert)}")
    print()

    if args.dry_run:
        # Show first 30 and last 5
        sample = to_insert[:30]
        for rec in sample:
            print(f"  [cat:{rec['category_id']}] {rec['name'][:60]:<60} -> {rec['filename']}")
        if len(to_insert) > 30:
            print(f"  ... and {len(to_insert)-30} more")
        print(f"\n[DRY RUN] Nothing written.")
        return

    # Insert
    inserted = 0
    failed = 0
    for rec in to_insert:
        safe_name = rec['name'].replace("'", "\\'")
        safe_slug = rec['slug'].replace("'", "\\'")
        safe_fn   = rec['filename'].replace("'", "\\'")
        sql = (
            f"INSERT IGNORE INTO plates (name, slug, series_id, category_id, image_filename, is_active, created_at, updated_at) "
            f"VALUES ('{safe_name}', '{safe_slug}', {args.series_id}, {rec['category_id']}, '{safe_fn}', 1, NOW(), NOW());"
        )
        if run_sql_exec(sql):
            inserted += 1
        else:
            failed += 1

    print(f"Inserted : {inserted}")
    print(f"Failed   : {failed}")
    print(f"Skipped  : {skipped_exists}")


if __name__ == '__main__':
    main()
