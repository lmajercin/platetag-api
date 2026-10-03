#!/usr/bin/env python3
"""Extract users CSV and discovery insights from a MySQL dump."""
from __future__ import annotations

import csv
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DUMP = Path(r"C:\Users\lmaje\OneDrive\Documents\platetag\database-sql\260820-platetag_db1.sql")
OUT_DIR = Path(r"C:\Users\lmaje\OneDrive\Documents\platetag\database-sql")
CSV_OUT = OUT_DIR / "users_email_export_2026-08-20.csv"


def split_sql_values(s: str) -> list[str]:
    """Split a MySQL VALUES row into fields, respecting quotes and escapes."""
    fields: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "'" or s[i] == '"':
            quote = s[i]
            i += 1
            buf: list[str] = []
            while i < n:
                if s[i] == "\\" and i + 1 < n:
                    buf.append(s[i + 1])
                    i += 2
                    continue
                if s[i] == quote:
                    if i + 1 < n and s[i + 1] == quote:
                        buf.append(quote)
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(s[i])
                i += 1
            fields.append("".join(buf))
        elif s[i] == "N" and s[i : i + 4] == "NULL":
            fields.append(None)  # type: ignore
            i += 4
        elif s[i] in ", ":
            i += 1
        else:
            # number / bare token until comma
            j = i
            while j < n and s[j] != ",":
                j += 1
            fields.append(s[i:j].strip())
            i = j
    return fields


def extract_insert_blocks(dump_path: Path, table: str) -> list[str]:
    """Yield raw VALUES payloads for INSERT INTO `table`."""
    marker = f"INSERT INTO `{table}`"
    blocks: list[str] = []
    with dump_path.open("r", encoding="utf-8", errors="replace") as fh:
        collecting = False
        buf: list[str] = []
        for line in fh:
            if line.startswith(marker):
                collecting = True
                buf = [line]
                if line.rstrip().endswith(";"):
                    blocks.append("".join(buf))
                    collecting = False
                    buf = []
                continue
            if collecting:
                buf.append(line)
                if line.rstrip().endswith(";"):
                    blocks.append("".join(buf))
                    collecting = False
                    buf = []
    return blocks


def parse_users(blocks: list[str]) -> list[dict]:
    # Column order from typical Laravel users dump — detect from INSERT header if present
    users = []
    for block in blocks:
        # INSERT INTO `users` (`col`, ...) VALUES (...),(...);
        m = re.match(r"INSERT INTO `users` \(([^)]+)\) VALUES\s*(.*);\s*$", block, re.S)
        if not m:
            # fallback: no column list
            m2 = re.match(r"INSERT INTO `users` VALUES\s*(.*);\s*$", block, re.S)
            if not m2:
                continue
            cols = None
            values_blob = m2.group(1)
        else:
            cols = [c.strip().strip("`") for c in m.group(1).split(",")]
            values_blob = m.group(2)

        # split rows: ),(
        rows = re.split(r"\),\s*\(", values_blob.strip())
        for idx, row in enumerate(rows):
            row = row.strip()
            if row.startswith("("):
                row = row[1:]
            if row.endswith(")"):
                row = row[:-1]
            fields = split_sql_values(row)
            if cols:
                if len(fields) < len(cols):
                    continue
                d = dict(zip(cols, fields))
            else:
                # guess common order: id, name, email, ...
                d = {"id": fields[0] if fields else None, "name": fields[1] if len(fields) > 1 else None, "email": fields[2] if len(fields) > 2 else None}
            users.append(d)
    return users


def split_name(name: str | None) -> tuple[str, str]:
    if not name:
        return "", ""
    name = name.strip()
    if not name:
        return "", ""
    parts = name.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def write_users_csv(users: list[dict], path: Path) -> int:
    # Prefer username column if present; else empty
    count = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["First Name", "Last Name", "Username", "Email"])
        for u in users:
            email = (u.get("email") or "").strip()
            if not email:
                continue
            first, last = split_name(u.get("name"))
            username = (u.get("username") or u.get("user_name") or "").strip()
            w.writerow([first, last, username, email])
            count += 1
    return count


def parse_discoveries(blocks: list[str]) -> list[dict]:
    rows_out = []
    for block in blocks:
        m = re.match(
            r"INSERT INTO `user_discovered_plates` \(([^)]+)\) VALUES\s*(.*);\s*$",
            block,
            re.S,
        )
        if not m:
            continue
        cols = [c.strip().strip("`") for c in m.group(1).split(",")]
        values_blob = m.group(2)
        rows = re.split(r"\),\s*\(", values_blob.strip())
        for row in rows:
            row = row.strip()
            if row.startswith("("):
                row = row[1:]
            if row.endswith(")"):
                row = row[:-1]
            fields = split_sql_values(row)
            if len(fields) < len(cols):
                continue
            rows_out.append(dict(zip(cols, fields)))
    return rows_out


def analyze(discoveries: list[dict], users: list[dict]) -> None:
    total = len(discoveries)
    with_loc = 0
    users_with_any_loc: set[str] = set()
    users_all: set[str] = set()
    by_day: Counter = Counter()
    by_hour: Counter = Counter()
    by_weekday: Counter = Counter()
    by_user: Counter = Counter()
    by_plate: Counter = Counter()
    by_session_null = 0
    lat_lons: list[tuple[float, float]] = []

    for d in discoveries:
        uid = str(d.get("user_id") or "")
        users_all.add(uid)
        by_user[uid] += 1
        by_plate[str(d.get("plate_id") or "")] += 1
        lat = d.get("latitude")
        lon = d.get("longitude")
        has = lat not in (None, "", "NULL") and lon not in (None, "", "NULL")
        if has:
            with_loc += 1
            users_with_any_loc.add(uid)
            try:
                lat_lons.append((float(lat), float(lon)))
            except ValueError:
                pass
        if not d.get("session_id") or d.get("session_id") in (None, "NULL", ""):
            by_session_null += 1
        disc = d.get("discovered_at") or ""
        # "YYYY-MM-DD HH:MM:SS"
        try:
            dt = datetime.strptime(disc[:19], "%Y-%m-%d %H:%M:%S")
            by_day[dt.strftime("%Y-%m-%d")] += 1
            by_hour[dt.hour] += 1
            by_weekday[dt.strftime("%A")] += 1
        except ValueError:
            pass

    print("=== DISCOVERY INSIGHTS ===")
    print(f"total_discoveries={total}")
    print(f"unique_users_with_discoveries={len(users_all)}")
    print(f"total_users_in_dump={len(users)}")
    pct_loc = (100.0 * with_loc / total) if total else 0
    print(f"discoveries_with_location={with_loc} ({pct_loc:.1f}%)")
    print(f"discoveries_without_location={total - with_loc} ({100 - pct_loc:.1f}%)")
    if users_all:
        pct_users_loc = 100.0 * len(users_with_any_loc) / len(users_all)
        print(
            f"users_who_ever_shared_location={len(users_with_any_loc)} "
            f"({pct_users_loc:.1f}% of users with discoveries)"
        )
        print(
            f"users_who_never_shared_location={len(users_all) - len(users_with_any_loc)} "
            f"({100 - pct_users_loc:.1f}%)"
        )
    print(f"discoveries_with_null_session={by_session_null}")

    # Top days
    print("\n--- Top 10 discovery days ---")
    for day, c in by_day.most_common(10):
        print(f"  {day}: {c}")

    print("\n--- Discoveries by weekday ---")
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for w in order:
        print(f"  {w}: {by_weekday.get(w, 0)}")

    print("\n--- Discoveries by hour (UTC server time) ---")
    for h in range(24):
        print(f"  {h:02d}: {by_hour.get(h, 0)}")

    print("\n--- Top 15 users by discovery count ---")
    for uid, c in by_user.most_common(15):
        print(f"  user_id={uid}: {c}")

    print("\n--- Top 15 plates by discovery count ---")
    for pid, c in by_plate.most_common(15):
        print(f"  plate_id={pid}: {c}")

    # Repeat discoveries (same user+plate more than once)
    pair = Counter()
    for d in discoveries:
        pair[(str(d.get("user_id")), str(d.get("plate_id")))] += 1
    repeats = sum(1 for v in pair.values() if v > 1)
    print(f"\nuser_plate_pairs={len(pair)} pairs_with_repeats={repeats}")

    # Rough geo clusters (1-degree bins)
    if lat_lons:
        bins = Counter()
        for lat, lon in lat_lons:
            bins[(round(lat), round(lon))] += 1
        print("\n--- Top geo bins (1-degree, rounded) ---")
        for (la, lo), c in bins.most_common(15):
            print(f"  lat~{la}, lon~{lo}: {c}")

    # Growth: first/last discovery
    days_sorted = sorted(by_day.keys())
    if days_sorted:
        print(f"\nfirst_discovery_day={days_sorted[0]} last={days_sorted[-1]}")
        # last 7 vs prior 7
        last7 = days_sorted[-7:]
        prior7 = days_sorted[-14:-7] if len(days_sorted) >= 14 else []
        s7 = sum(by_day[d] for d in last7)
        s14 = sum(by_day[d] for d in prior7) if prior7 else 0
        print(f"discoveries_last_7_days={s7} prior_7_days={s14}")


def main() -> int:
    if not DUMP.exists():
        print(f"Dump not found: {DUMP}", file=sys.stderr)
        return 1
    print(f"Dump size bytes={DUMP.stat().st_size}")

    print("Extracting users...")
    user_blocks = extract_insert_blocks(DUMP, "users")
    print(f"user INSERT blocks={len(user_blocks)}")
    users = parse_users(user_blocks)
    print(f"parsed users={len(users)}")
    n = write_users_csv(users, CSV_OUT)
    print(f"CSV written: {CSV_OUT} rows={n}")

    # show columns from first user
    if users:
        print("user columns:", sorted(users[0].keys()))

    print("\nExtracting discoveries...")
    disc_blocks = extract_insert_blocks(DUMP, "user_discovered_plates")
    print(f"discovery INSERT blocks={len(disc_blocks)}")
    discoveries = parse_discoveries(disc_blocks)
    print(f"parsed discoveries={len(discoveries)}")
    if discoveries:
        print("discovery columns:", sorted(discoveries[0].keys()))
        analyze(discoveries, users)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
