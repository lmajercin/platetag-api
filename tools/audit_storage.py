#!/usr/bin/env python3
"""
audit_storage.py
================
Cross-references every plate in the DB that has an image_filename against
the Laravel storage folder. Reports:
  - MISSING : filename in DB, file not in storage
  - ORPHAN  : file in storage, no DB plate references it
  - NULL    : plates with no image_filename at all (grouped by state)

Usage:
  python tools/audit_storage.py
  python tools/audit_storage.py --state pa   # limit to one state
  python tools/audit_storage.py --missing-only
"""

import argparse
import subprocess
import sys
from pathlib import Path

MYSQL   = Path(r'C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe')
DB_USER = 'root'
DB_PASS = r'4rfv$RFV'
DB_NAME = 'platetag_api'
STORAGE = Path(r'C:\wamp64\www\platetag-api\storage\app\public\plates')


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', help='Filter to a single state code (e.g. pa, or, ca)')
    parser.add_argument('--missing-only', action='store_true', help='Only show MISSING files')
    args = parser.parse_args()

    state_filter = f"AND r.code = '{args.state.lower()}'" if args.state else ''

    # All plates with images
    rows = run_sql(f"""
        SELECT p.id, p.slug, p.image_filename, r.code AS state
        FROM plates p
        JOIN series s ON s.id = p.series_id
        JOIN regions r ON r.id = s.region_id
        WHERE p.image_filename IS NOT NULL AND p.image_filename != ''
        {state_filter}
        ORDER BY r.code, p.slug
    """)

    # All plates with no image
    null_rows = run_sql(f"""
        SELECT r.code AS state, COUNT(*) AS cnt
        FROM plates p
        JOIN series s ON s.id = p.series_id
        JOIN regions r ON r.id = s.region_id
        WHERE (p.image_filename IS NULL OR p.image_filename = '')
        {state_filter}
        GROUP BY r.code
        ORDER BY r.code
    """)

    # Build set of all storage files
    storage_files = {f.name for f in STORAGE.iterdir() if f.is_file()}
    db_referenced = set()

    missing = []
    found = 0

    for row in rows:
        fn = row['image_filename']
        db_referenced.add(fn)
        if STORAGE.joinpath(fn).exists():
            found += 1
        else:
            missing.append(row)

    orphans = storage_files - db_referenced

    # === Report ===
    print(f"{'='*60}")
    print(f"STORAGE AUDIT REPORT")
    print(f"{'='*60}")
    print(f"DB plates with image    : {len(rows)}")
    print(f"Files found in storage  : {found}")
    print(f"MISSING (DB has, no file): {len(missing)}")
    print(f"ORPHAN files (no DB ref): {len(orphans)}")
    print()

    if missing:
        print(f"{'='*60}")
        print("MISSING FILES (plate has image_filename but file not found)")
        print(f"{'='*60}")
        by_state: dict[str, list] = {}
        for r in missing:
            by_state.setdefault(r['state'], []).append(r)
        for state in sorted(by_state):
            print(f"\n[{state.upper()}] {len(by_state[state])} missing")
            for r in by_state[state]:
                print(f"  id={r['id']:<5} {r['slug'][:55]:<55} -> {r['image_filename']}")

    if not args.missing_only and orphans:
        print(f"\n{'='*60}")
        print(f"ORPHAN FILES IN STORAGE (no plate references them)")
        print(f"{'='*60}")
        for f in sorted(orphans):
            print(f"  {f}")

    if null_rows:
        print(f"\n{'='*60}")
        print("PLATES WITH NO IMAGE (NULL or empty image_filename)")
        print(f"{'='*60}")
        for r in null_rows:
            print(f"  {r['state'].upper():<5} : {r['cnt']} plates")

    print()
    print("Done.")


if __name__ == '__main__':
    main()
