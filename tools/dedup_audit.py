"""
dedup_audit.py  —  PlateTag duplicate detection & deactivation tool
====================================================================
PHASE 1 (default): Generates audit CSV. No DB changes.
PHASE 2 (--execute): Applies deactivations and slug fixes after review.

Duplicate logic:
  - Finds plates whose slug = base_slug + '-v1' (or -v2, -v3...)
  - For each group, compares image file sizes on disk
  - Keeps: largest image. Tie: prefer the one with ' - ' format in name.
  - Deactivates losers (is_active = 0). Never deletes.
  - If winner's slug has a -v1 suffix AND the old plate is being deactivated,
    updates winner's slug to the clean base slug.

Three-way groups (old + v1 + v2):
  - These are flagged as REVIEW in the CSV — not auto-processed.
  - Likely legitimately different plate designs.

Usage:
  python dedup_audit.py              # audit only, writes dedup_audit.csv
  python dedup_audit.py --execute    # apply changes (requires audit CSV exists first)
"""

import os
import sys
import csv
import re
import mysql.connector
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DB_HOST     = '127.0.0.1'
DB_PORT     = 3306
DB_USER     = 'root'
DB_PASSWORD = '4rfv$RFV'
DB_NAME     = 'platetag_api'
IMAGE_DIR   = r'C:\wamp64\www\platetag-api\storage\app\public\plates'
AUDIT_CSV   = r'C:\wamp64\www\platetag-api\tools\dedup_audit.csv'
# ──────────────────────────────────────────────────────────────────────────────

EXECUTE = '--execute' in sys.argv


def connect():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME
    )


def image_size(filename):
    """Return file size in bytes, or 0 if file not found."""
    if not filename:
        return 0
    path = os.path.join(IMAGE_DIR, filename)
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def has_spaced_dash(name):
    """True if name uses ' - ' (space-dash-space) after the state code."""
    # Matches: 'XX - ' at the start
    return bool(re.match(r'^[A-Za-z]{2} - ', name))


def fetch_all_plates(cursor):
    cursor.execute("""
        SELECT id, name, slug, image_filename, is_active
        FROM plates
        ORDER BY slug, id
    """)
    return cursor.fetchall()


def build_groups(plates):
    """
    Group plates by their base slug.
    A base slug is any slug that does NOT end in -v1, -v2, -v3 etc.
    Variants are slugs that equal base + '-v1', '-v2', '-v3'.
    Returns list of (base_plate, [variant_plates])
    """
    slug_map = {row['slug']: row for row in plates}
    grouped = {}  # base_slug -> {'base': row, 'variants': [row, ...]}

    for row in plates:
        slug = row['slug']
        # Check if this slug is a variant of another slug
        m = re.match(r'^(.+)-v(\d+)$', slug)
        if m:
            base_slug = m.group(1)
            if base_slug in slug_map:
                if base_slug not in grouped:
                    grouped[base_slug] = {'base': slug_map[base_slug], 'variants': []}
                grouped[base_slug]['variants'].append(row)

    return grouped


def decide(base, variants):
    """
    For a group of (base + variants), decide what action to take.
    Returns list of dicts: {id, action, reason, new_slug}
    Actions: KEEP, DEACTIVATE, REVIEW
    """
    all_plates = [base] + variants

    if len(variants) > 1:
        # Three or more total — flag for manual review
        return [{'id': p['id'], 'name': p['name'], 'slug': p['slug'],
                 'image_filename': p['image_filename'],
                 'image_size': image_size(p['image_filename']),
                 'action': 'REVIEW',
                 'reason': f'{len(variants)} variants found — manual review needed',
                 'new_slug': ''} for p in all_plates]

    # Exactly one variant — simple pair
    variant = variants[0]
    base_size    = image_size(base['image_filename'])
    variant_size = image_size(variant['image_filename'])

    # Determine winner
    if base_size > variant_size:
        winner, loser = base, variant
        reason = f'old image larger ({base_size} vs {variant_size} bytes)'
    elif variant_size > base_size:
        winner, loser = variant, base
        reason = f'new image larger ({variant_size} vs {base_size} bytes)'
    else:
        # Tie — prefer spaced format
        if has_spaced_dash(variant['name']):
            winner, loser = variant, base
            reason = f'equal size ({base_size} bytes) — new uses preferred " - " format'
        else:
            winner, loser = base, variant
            reason = f'equal size ({base_size} bytes) — old retained (neither uses preferred format)'

    # If winner is the variant (has -v1 slug), its slug should be cleaned to base slug
    new_slug = ''
    if winner['id'] == variant['id']:
        new_slug = base['slug']  # winner takes over the clean slug

    return [
        {'id': winner['id'], 'name': winner['name'], 'slug': winner['slug'],
         'image_filename': winner['image_filename'],
         'image_size': image_size(winner['image_filename']),
         'action': 'KEEP', 'reason': reason, 'new_slug': new_slug},
        {'id': loser['id'], 'name': loser['name'], 'slug': loser['slug'],
         'image_filename': loser['image_filename'],
         'image_size': image_size(loser['image_filename']),
         'action': 'DEACTIVATE', 'reason': reason, 'new_slug': ''},
    ]


def run_audit():
    conn = connect()
    cursor = conn.cursor(dictionary=True)
    plates = fetch_all_plates(cursor)
    cursor.close()
    conn.close()

    print(f"Total plates: {len(plates)}")

    groups = build_groups(plates)
    print(f"Duplicate groups found: {len(groups)}")

    rows = []
    keep_count = 0
    deactivate_count = 0
    review_count = 0

    for base_slug, group in sorted(groups.items()):
        decisions = decide(group['base'], group['variants'])
        for d in decisions:
            rows.append(d)
            if d['action'] == 'KEEP':        keep_count += 1
            elif d['action'] == 'DEACTIVATE': deactivate_count += 1
            elif d['action'] == 'REVIEW':     review_count += 1

    with open(AUDIT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'action', 'id', 'name', 'slug', 'image_filename',
            'image_size', 'reason', 'new_slug'
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nAudit complete:")
    print(f"  KEEP:       {keep_count}")
    print(f"  DEACTIVATE: {deactivate_count}")
    print(f"  REVIEW:     {review_count} (manual action required)")
    print(f"\nCSV written to: {AUDIT_CSV}")
    print("Review the CSV, then run with --execute to apply changes.")


def run_execute():
    if not os.path.exists(AUDIT_CSV):
        print("ERROR: Audit CSV not found. Run without --execute first.")
        sys.exit(1)

    with open(AUDIT_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    deactivate_rows = [r for r in rows if r['action'] == 'DEACTIVATE']
    slug_update_rows = [r for r in rows if r['action'] == 'KEEP' and r['new_slug']]
    review_rows = [r for r in rows if r['action'] == 'REVIEW']

    print(f"Will deactivate: {len(deactivate_rows)} plates")
    print(f"Will update slugs: {len(slug_update_rows)} plates")
    print(f"Skipping REVIEW rows: {len(review_rows)} (manual action required)")

    confirm = input("\nType YES to proceed: ")
    if confirm.strip() != 'YES':
        print("Aborted.")
        sys.exit(0)

    conn = connect()
    cursor = conn.cursor()

    deactivated = 0
    for r in deactivate_rows:
        cursor.execute(
            "UPDATE plates SET is_active = 0, updated_at = NOW() WHERE id = %s",
            (r['id'],)
        )
        deactivated += 1

    slug_updated = 0
    for r in slug_update_rows:
        # Only update slug if the new_slug is not already taken by an active plate
        cursor.execute(
            "SELECT COUNT(*) FROM plates WHERE slug = %s AND id != %s AND is_active = 1",
            (r['new_slug'], r['id'])
        )
        (conflict_count,) = cursor.fetchone()
        if conflict_count == 0:
            cursor.execute(
                "UPDATE plates SET slug = %s, updated_at = NOW() WHERE id = %s",
                (r['new_slug'], r['id'])
            )
            slug_updated += 1
        else:
            print(f"  SLUG CONFLICT skipped: plate {r['id']} → '{r['new_slug']}' already taken")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nDone.")
    print(f"  Deactivated: {deactivated} plates")
    print(f"  Slugs updated: {slug_updated} plates")
    if review_rows:
        print(f"  REVIEW rows: {len(review_rows)} — open {AUDIT_CSV} and handle manually")


if __name__ == '__main__':
    if EXECUTE:
        run_execute()
    else:
        run_audit()
