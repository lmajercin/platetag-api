#!/usr/bin/env python3
"""
match_null_images.py
====================
For every plate with NULL/empty image_filename, scans the image archive
to find a file whose name (stripped of extension and normalized) matches
or closely matches the plate's slug (stripped of state prefix).

When a confident match is found it either:
  --dry-run : prints the proposed match
  --apply   : updates the DB + copies the file to storage if not already there

Usage:
  python tools/match_null_images.py --state ca --dry-run
  python tools/match_null_images.py --state co --apply
  python tools/match_null_images.py --apply          # all states
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MYSQL   = Path(r'C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe')
DB_USER = 'root'
DB_PASS = r'4rfv$RFV'
DB_NAME = 'platetag_api'
ARCHIVE = Path(r'\\driveby_NAS\Plex\Larry Doc\Plates\assets\images')
STORAGE = Path(r'C:\wamp64\www\platetag-api\storage\app\public\plates')

# When the archive drive is unavailable, fall back to matching against
# files already in storage (covers orphaned files and previously synced assets)
USE_STORAGE_FALLBACK = not os.path.exists(str(ARCHIVE))

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


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


def normalize(s: str) -> str:
    """Lowercase, strip extension, collapse non-alphanumeric to single hyphen."""
    s = re.sub(r'\.[a-z]{2,4}$', '', s.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def slug_key(slug: str, state_name: str) -> str:
    """Strip the state name prefix from a slug for matching."""
    # Convert state name to slug form, e.g. 'California' -> 'california'
    state_prefix = normalize(state_name) + '-'
    if slug.startswith(state_prefix):
        return slug[len(state_prefix):]
    return slug


def build_archive_index(state_code: str) -> dict[str, Path]:
    """
    Index all image files under the state's archive subfolder (or storage fallback).
    Keys are normalized stems with the state prefix stripped, e.g.:
      ca-firefighter-passenger.gif  ->  'firefighter-passenger'
    Returns {normalized_key: Path}
    """
    prefix = state_code.lower() + '-'

    def index_file(f: Path, index: dict) -> None:
        norm = normalize(f.stem)
        # Strip state prefix from the normalized stem so it matches slug_key output
        if norm.startswith(prefix):
            norm = norm[len(prefix):]
        if norm not in index:
            index[norm] = f

    if USE_STORAGE_FALLBACK:
        index: dict[str, Path] = {}
        for f in STORAGE.iterdir():
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS and f.name.lower().startswith(prefix):
                index_file(f, index)
        return index

    state_dir = ARCHIVE / state_code.lower()
    if not os.path.exists(str(state_dir)):
        return {}
    index: dict[str, Path] = {}
    for f in state_dir.rglob('*'):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            index_file(f, index)
    return index


def find_match(key: str, index: dict[str, Path]) -> Path | None:
    """Exact match first, then try dropping trailing vehicle-type suffixes."""
    if key in index:
        return index[key]
    # Try dropping common suffixes: -passenger, -motorcycle, -version-1, etc.
    for suffix in ('-passenger', '-motorcycle', '-motorcycle-pwd', '-passenger-pwd',
                   '-version-1', '-version-2', '-version-3', '-auto', '-standard'):
        trimmed = key
        if trimmed.endswith(suffix):
            trimmed = trimmed[: -len(suffix)]
            if trimmed in index:
                return index[trimmed]
    # Try adding common suffixes
    for suffix in ('-passenger', '-auto', '-standard'):
        candidate = key + suffix
        if candidate in index:
            return index[candidate]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', help='Two-letter state code (default: all)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        sys.exit('Specify --dry-run or --apply')

    state_filter = f"AND r.code = '{args.state.lower()}'" if args.state else ''

    rows = run_sql(f"""
        SELECT p.id, p.slug, r.code AS state, r.name AS state_name
        FROM plates p
        JOIN series s ON s.id = p.series_id
        JOIN regions r ON r.id = s.region_id
        WHERE (p.image_filename IS NULL OR p.image_filename = '')
        {state_filter}
        ORDER BY r.code, p.slug
    """)

    print(f"Null-image plates to match: {len(rows)}\n")

    matched = skipped = failed = 0
    current_state = None
    archive_index: dict[str, Path] = {}

    for row in rows:
        state = row['state']
        if state != current_state:
            current_state = state
            archive_index = build_archive_index(state)

        key = slug_key(row['slug'], row['state_name'])
        hit = find_match(key, archive_index)

        if hit is None:
            print(f"  [NO MATCH] {row['slug']}")
            skipped += 1
            continue

        dest_name = hit.name
        print(f"  [MATCH] {row['slug']}")
        print(f"          {dest_name}")

        if args.dry_run:
            continue

        # Copy to storage if not already there (skip if using storage as source)
        dest_path = STORAGE / dest_name
        if not dest_path.exists():
            shutil.copy2(hit, dest_path)

        safe_fn = dest_name.replace("'", "\\'")
        sql = f"UPDATE plates SET image_filename = '{safe_fn}' WHERE id = {row['id']}"
        if run_sql_exec(sql):
            matched += 1
        else:
            failed += 1

    print()
    if args.apply:
        print(f"Matched  : {matched}")
        print(f"No match : {skipped}")
        print(f"Failed   : {failed}")
    else:
        print("[DRY RUN] Nothing written.")


if __name__ == '__main__':
    main()
