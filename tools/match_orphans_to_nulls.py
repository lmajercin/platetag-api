#!/usr/bin/env python3
"""
match_orphans_to_nulls.py
========================
Matches orphan storage files to NULL-image DB plates.

For each orphan file in storage (no plate references it), try to find a
NULL-image plate in the same state whose slug key matches the orphan's
normalized filename key.

State detection: extracts leading 2-letter code from filename
  e.g. ca-artist.jpg -> 'ca', OR053_Cultural_Trust.png -> 'or', ny-dealer.png -> 'ny'

Usage:
  python tools/match_orphans_to_nulls.py --dry-run
  python tools/match_orphans_to_nulls.py --apply
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

MYSQL   = Path(r'C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe')
DB_USER = 'root'
DB_PASS = r'4rfv$RFV'
DB_NAME = 'platetag_api'
STORAGE = Path(r'C:\wamp64\www\platetag-api\storage\app\public\plates')

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


def extract_state_and_key(filename: str) -> tuple[str, str] | None:
    """
    Given a filename, extract the 2-letter state code and a normalized key.
    Handles patterns like:
      ca-firefighter.jpg       -> ('ca', 'firefighter')
      OR053_Cultural_Trust.png -> ('or', '053-cultural-trust')  (num prefix stays)
      ny-dealer.png            -> ('ny', 'dealer')
    Returns None if no state prefix found.
    """
    stem = Path(filename).stem
    norm = normalize(stem)

    # Match leading 2-letter state code followed by hyphen or digits
    m = re.match(r'^([a-z]{2})[-_0-9]', norm)
    if m:
        code = m.group(1)
        rest = norm[len(code):]
        rest = re.sub(r'^[-_0-9]+', '', rest).strip('-')
        return code, rest
    return None


def build_null_index(rows: list[dict]) -> dict[str, list[dict]]:
    """
    Build index: state_code -> list of {id, slug, key} for NULL-image plates.
    Key is the slug with the full state name prefix stripped.
    """
    idx: dict[str, list[dict]] = {}
    for row in rows:
        state_code = row['state'].lower()
        # Strip full state name from slug (e.g. 'california-' from slug)
        state_prefix = normalize(row['state_name']) + '-'
        slug = row['slug']
        key = slug[len(state_prefix):] if slug.startswith(state_prefix) else slug
        entry = {'id': row['id'], 'slug': slug, 'key': key, 'filename': row['filename']}
        idx.setdefault(state_code, []).append(entry)
    return idx


def get_ref_filenames() -> set[str]:
    """Get all image_filename values currently referenced by plates."""
    rows = run_sql("SELECT image_filename FROM plates WHERE image_filename IS NOT NULL AND image_filename != ''")
    return {r['image_filename'] for r in rows}


def get_orphans(ref_filenames: set[str]) -> list[Path]:
    """Return storage files not referenced by any plate."""
    orphans = []
    for f in STORAGE.iterdir():
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            if f.name not in ref_filenames:
                orphans.append(f)
    return sorted(orphans)


def cosine_overlap(a: str, b: str) -> float:
    """Simple word-overlap score between two hyphen-delimited strings."""
    wa = set(a.split('-'))
    wb = set(b.split('-'))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def find_best_match(orphan_key: str, null_plates: list[dict]) -> dict | None:
    """
    Find the best NULL plate match for an orphan key.
    Exact match wins; then partial key containment; finally word overlap >= 0.5.
    """
    # Exact match
    for p in null_plates:
        if p['key'] == orphan_key:
            return p

    # Orphan key is contained in plate key or vice versa (prefix match)
    for p in null_plates:
        if orphan_key in p['key'] or p['key'] in orphan_key:
            return p

    # High word overlap
    best_score = 0.0
    best = None
    for p in null_plates:
        score = cosine_overlap(orphan_key, p['key'])
        if score > best_score:
            best_score = score
            best = p
    if best_score >= 0.5:
        return best

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--min-score', type=float, default=0.5,
                        help='Minimum word-overlap score for fuzzy matches (default 0.5)')
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        sys.exit('Specify --dry-run or --apply')

    # Fetch all NULL plates
    rows = run_sql("""
        SELECT p.id, p.slug, r.code AS state, r.name AS state_name,
               p.image_filename AS filename
        FROM plates p
        JOIN series s ON s.id = p.series_id
        JOIN regions r ON r.id = s.region_id
        WHERE (p.image_filename IS NULL OR p.image_filename = '')
        ORDER BY r.code, p.slug
    """)
    null_idx = build_null_index(rows)
    print(f"NULL-image plates: {len(rows)}")

    # Fetch current referenced filenames and compute orphans
    ref_fns = get_ref_filenames()
    orphans = get_orphans(ref_fns)
    print(f"Orphan files in storage: {len(orphans)}\n")

    matched = skipped = failed = 0

    for orphan in orphans:
        result = extract_state_and_key(orphan.name)
        if result is None:
            print(f"  [SKIP - no state prefix] {orphan.name}")
            skipped += 1
            continue

        state_code, orphan_key = result
        null_plates = null_idx.get(state_code, [])
        if not null_plates:
            print(f"  [SKIP - no NULL plates for {state_code.upper()}] {orphan.name}")
            skipped += 1
            continue

        hit = find_best_match(orphan_key, null_plates)
        if hit is None:
            print(f"  [NO MATCH] {orphan.name!r:55s} key={orphan_key!r}")
            skipped += 1
            continue

        print(f"  [MATCH] {orphan.name!r:55s} -> {hit['slug']!r}")
        if args.dry_run:
            continue

        safe_fn = orphan.name.replace("'", "\\'")
        sql = f"UPDATE plates SET image_filename = '{safe_fn}' WHERE id = {hit['id']}"
        if run_sql_exec(sql):
            matched += 1
        else:
            failed += 1

    print()
    if args.apply:
        print(f"Matched : {matched}")
        print(f"Skipped : {skipped}")
        print(f"Failed  : {failed}")
    else:
        print("[DRY RUN] Nothing written.")


if __name__ == '__main__':
    main()
