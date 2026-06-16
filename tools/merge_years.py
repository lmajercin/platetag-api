#!/usr/bin/env python3
"""
merge_years.py
==============
Merges AI-generated year data back into a full plates import CSV.

The AI typically returns only: plate_number, year_introduced, year_discontinued
This script patches those year columns into the full 14-column converter output.

Usage:
    python merge_years.py full_import.csv ai_years.csv output.csv

Arguments:
    full_import.csv  - 14-column CSV produced by convert_plates_csv.py
    ai_years.csv     - 2-3 column CSV from AI (plate_number, year_introduced, [year_discontinued])
    output.csv       - Merged output (same file as full_import.csv is OK)

Example:
    python merge_years.py md_plates_import_full.csv md_ai_years.csv md_plates_import.csv
"""

import csv
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 4:
        print("Usage: python merge_years.py full_import.csv ai_years.csv output.csv")
        sys.exit(1)

    full_path = Path(sys.argv[1])
    ai_path   = Path(sys.argv[2])
    out_path  = Path(sys.argv[3])

    # ── Load AI year data keyed by plate_number ───────────────────────────────
    ai_years = {}
    with open(ai_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Normalise header names
        for row in reader:
            key = row.get('plate_number', row.get('Plate Number', '')).strip()
            if not key:
                continue
            yr_intro = row.get('year_introduced', row.get('Year Introduced', '')).strip()
            yr_disco = row.get('year_discontinued', row.get('Year Discontinued', '')).strip()
            ai_years[key] = (yr_intro, yr_disco)

    print(f"Loaded {len(ai_years)} year entries from AI file.")

    # ── Read full CSV and patch years ─────────────────────────────────────────
    with open(full_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    matched   = 0
    unmatched = []

    for row in rows:
        pn = row['plate_number'].strip()
        if pn in ai_years:
            yr_intro, yr_disco = ai_years[pn]
            if yr_intro:
                row['year_introduced'] = yr_intro
            if yr_disco:
                row['year_discontinued'] = yr_disco
            matched += 1
        else:
            unmatched.append(pn)

    # ── Write output ──────────────────────────────────────────────────────────
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Matched and updated : {matched}")
    print(f"No AI data found for: {len(unmatched)}")
    if unmatched:
        print("  Unmatched plates (years left blank):")
        for p in unmatched[:20]:
            print(f"    {p}")
        if len(unmatched) > 20:
            print(f"    … and {len(unmatched) - 20} more")
    print(f"\nOutput written to: {out_path}")


if __name__ == '__main__':
    main()
