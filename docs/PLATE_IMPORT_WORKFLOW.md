# Plate Bulk Import Workflow

Complete step-by-step reference for converting a raw plate data CSV, acquiring
images, and importing everything into the License Plate Collector database —
both locally (WAMP) and on production (A2 Hosting).

---

## Overview

```
Raw data CSV  ──►  Python converter  ──►  Import CSV
                                              │
                       ChatGPT (year fill)  ──┤
                                              │
                       Image download        ──┤
                                              │
                       Move images to        ──┤
                       uploads/plate/         │
                                              ▼
                              Admin UI  ──►  Dry Run  ──►  Commit (insert)
                                                 ▼
                                          Re-run CSV  ──►  Commit (image link)
```

---

## Prerequisites

| Tool | Notes |
|---|---|
| Python 3.7+ | `python --version` to verify |
| WAMP running | Apache + MySQL must be active |
| Admin account | Must be an admin user in the app |
| `convert_plates_csv.py` | Located in `tools/` |
| Raw source CSV | Keegan/DMV format — columns: `State`, `Description`, `Plate Image`, `Source` |

---

## Step 1 — Obtain the Source CSV

The source data comes from the Keegan public dataset (one CSV file covering all
US states).  Each row has this format:

| State | Description | Plate Image | Source |
|---|---|---|---|
| CA | California - Amateur Radio Call Letters - Block | `![Plate](https://…/AmRadioblock.gif)` | … |

Save the raw CSV somewhere accessible, e.g.:
```
P:\Larry Doc\Plates\assets\images\continent\north_america\usa\data-RwS5X.csv
```

---

## Step 2 — Run the Python Converter

Open the **Python terminal** in VS Code (or any terminal with Python on PATH).

### Basic conversion (no image download)
```powershell
python "c:\wamp64\www\platetag-api\tools\convert_plates_csv.py" `
    "P:\Larry Doc\Plates\assets\images\continent\north_america\usa\data-RwS5X.csv" `
    "c:\wamp64\www\platetag-api\tools\XX_plates_import.csv" `
    --state XX
```
Replace `XX` with the two-letter state code (e.g. `CA`, `MD`, `TX`).

### With image download (recommended)
```powershell
python "c:\wamp64\www\platetag-api\tools\convert_plates_csv.py" `
    "P:\Larry Doc\Plates\assets\images\continent\north_america\usa\data-RwS5X.csv" `
    "c:\wamp64\www\platetag-api\tools\XX_plates_import.csv" `
    --state XX `
    --download-images "P:\Larry Doc\Plates\assets\images\XX"
```
Images download into `P:\Larry Doc\Plates\assets\images\XX\xx\` as
kebab-case filenames, e.g. `ca-amateur-radio-call-letters-block.gif`.

### What the converter does
- Filters rows to the requested state
- Parses `Description` into `plate_number` (`CA-Name-Variant` format)
- Infers `category_name` from keywords in the plate name
- Maps CA variant suffixes to DB series names (Block → `CA02-…`, Script → `CA01-…`, etc.)
- Downloads images if `--download-images` is given; skips already-downloaded files
- Writes `year_introduced`, `year_discontinued`, and `description` as **blank** — to be filled by AI (see Step 3)

### Output columns
```
plate_number, region_name, category_name, series_name,
description, year_introduced, year_discontinued, is_active,
plate_header, plate_base, plate_serial, plate_footer,
image_url, image_filename
```

---

## Step 3 — Fill Year Data with an AI Agent

The converter leaves `year_introduced` and `year_discontinued` blank.  An AI
agent (ChatGPT, Claude, DeepSeek, etc.) can fill those fields from its knowledge
of DMV plate history.

> **The #1 mistake:** Asking the AI for years without structure instructions
> causes it to return only 2–3 columns and discard the rest of your data.
> The prompt below prevents this — use it verbatim.

---

### Prompt template — copy this exactly

Open `tools/XX_plates_import_full.csv` and copy the **entire file contents**
(header row + all data rows).  Paste it into the chat and then send this prompt:

```
You are a data-fill assistant for US license plate history.
I am giving you a CSV file. Follow these rules exactly:

1. Return the COMPLETE CSV — every row, every column, in the original order.
2. Do NOT drop, reorder, rename, or add any columns.
3. Fill in ONLY the `year_introduced` and `year_discontinued` columns.
4. Use 4-digit years (1900–2026). Leave a cell empty if unknown.
5. `year_discontinued` must be ≥ `year_introduced`.
   If a plate is currently issued, leave `year_discontinued` empty.
6. Output raw CSV only — no markdown fences, no commentary, no explanation.
7. The header row must appear exactly once as the first line.

Here is the CSV:
[paste the full file contents here]
```

---

### Batch strategy for large states (> 150 rows)

AI context windows have size limits.  For states with many plates:

1. Split the CSV into batches of **100–150 rows each**.
2. Include the **header row** in every single batch — the AI needs it as
   a schema reference to know which columns are which.
3. Submit each batch with the same prompt above.
4. After the AI returns each batch, verify it still contains all 14 columns
   before saving.
5. Reassemble: append batch 2 onward **without** the header line into one file.

> **Tip:** Save each AI response as `XX_ai_batch_1.csv`, `XX_ai_batch_2.csv`,
> etc.  If reassembly is tedious, use `merge_years.py` (see below) to combine
> them with the original file instead.

---

### Fallback — merge_years.py

If the AI still returns only 3 columns despite the prompt, **do not overwrite
your full CSV**.  Save the AI output as `XX_ai_years.csv`, then run:

```powershell
python "c:\wamp64\www\platetag-api\tools\merge_years.py" `
    "c:\wamp64\www\platetag-api\tools\XX_plates_import_full.csv" `
    "c:\wamp64\www\platetag-api\tools\XX_ai_years.csv" `
    "c:\wamp64\www\platetag-api\tools\XX_plates_import.csv"
```

This merges the year data back into the 14-column file and writes
`XX_plates_import.csv` ready for the importer.  It reports matched/unmatched
counts — unmatched rows are left with blank years, which the importer accepts.

**Name convention:**
| File | Purpose |
|---|---|
| `XX_plates_import_full.csv` | Converter output — 14 columns, blank years |
| `XX_ai_years.csv` | Raw AI response (3-col fallback only) — **never overwrite the full file with this** |
| `XX_plates_import.csv` | Final merged file — ready to import |

---

### Validate the years

After filling years (by either method), do a quick scan:
- 4-digit years only (1900–2026)
- `year_discontinued` ≥ `year_introduced`
- Blank = unknown or currently issued (both are accepted by the importer)

---

## Step 4 — Move Images to the Upload Folder

### Local (WAMP)
Copy (or move) the downloaded images from the download folder into:
```
C:\wamp64\www\platetag-api\storage\app\public\plates\
```
Do **not** rename them — the filenames in the CSV's `image_filename` column must
match exactly.

Example:
```powershell
Copy-Item "P:\Larry Doc\Plates\assets\images\XX\xx\*.gif" `
    "C:\wamp64\www\platetag-api\storage\app\public\plates\"
Copy-Item "P:\Larry Doc\Plates\assets\images\XX\xx\*.jpg" `
    "C:\wamp64\www\platetag-api\storage\app\public\plates\"
Copy-Item "P:\Larry Doc\Plates\assets\images\XX\xx\*.png" `
    "C:\wamp64\www\platetag-api\storage\app\public\plates\"
```

You do **not** need to create thumbnails manually — the importer generates them
automatically during the image-link step.

### Production (A2 Hosting)
Upload images via FileZilla/SFTP into:
```
/home/platetag/platetag-api/storage/app/public/plates/
```
Same rule: filenames must match exactly.

---

## Step 5 — Verify the DB Has the Region

Log into the Admin Panel → **Regions** tab and confirm the target state/region
exists and is set to **active**.  If it's missing, add it before importing.

Similarly check that all `category_name` values from the CSV exist in
**Categories**.  Common categories used by the converter:

`Standard`, `Veteran`, `Government`, `Dealer`, `Apportioned`, `Radio`,
`Schools`, `Sports`, `Civic`, `Outdoors`, `Vintage`, `Handicapped`,
`Occupational`, `Specialty Equip`

---

> ⚠️ **Steps 6–10 below describe the old PHP import system.** They have not been updated for Filament yet.
> When you are ready to do a new state import, ask the agent to walk you through the current Filament-based import process.
> The tool paths in Steps 1–5 have been updated to `platetag-api/tools/` and are current.

## Step 6 — Dry Run in the Admin UI

1. Open the Filament admin: `http://localhost/platetag-api/public/admin`
2. Log in as an admin user
3. Navigate to the Plates import section
4. Click **Choose File** and select `tools/XX_plates_import.csv`
5. Click **Next: Preview** — review the first 5 rows
6. Click **Run Dry Run**

**Read the Validation Results:**

| Badge | Meaning |
|---|---|
| `✓ valid` | Row will be inserted as a new plate |
| `image linked` | Plate already exists; image will be linked |
| `skipped` | Plate already exists and already has an image — no action |
| `error` | Row has a problem (shown in the Message column) |

Fix any `error` rows in the CSV (bad year, unknown region, etc.) and re-run
the dry run until all rows are either `valid`, `image linked`, or acceptable
skips.

---

## Step 7 — Commit the Import

Once the dry run looks clean, click **Import All N Rows**.

The importer will:
- Insert new plate records into the `plates` table
- For existing plates with no image: run `UPDATE plates SET image_path = …`
  and generate a 150px thumbnail into `uploads/plate/thumbnails/`
- Skip plates that already have images

The **Import Complete** screen shows:
- `Inserted: N` — new plate rows added
- `Images linked: N` — existing plates that got images attached

---

## Step 8 — Two-Pass Workflow (New State)

For a brand-new state where plates don't exist yet:

**Pass 1 — Insert plates (no images yet)**
```
Dry Run → Commit
```
All rows show `✓ valid` and are inserted.  Images are linked if already in the
upload folder.  If images weren't copied yet, proceed to Pass 2.

**Pass 2 — Link images (after copying files)**
Re-upload the same CSV.
```
Dry Run → shows "image linked" for all rows → Commit
```
All plates get `image_path` + auto-generated thumbnail.

---

## Step 9 — Verify Results

1. Open the public plate list (or admin Plates panel) and spot-check a few CA entries
2. Confirm image thumbnails render in the list view
3. Click a plate → verify full image and all metadata are correct
4. Check `uploads/plate/thumbnails/` — should have a matching file for each linked image

---

## Step 10 — Promote to Production

> Do this only after the local import is fully verified.

### Files to FTP/deploy

| Local path | Production path |
|---|---|
| `backend/api/plates/import-csv.php` | `/public_html/plates_react/backend/api/plates/import-csv.php` |
| `backend/api/bootstrap.php` | `/public_html/plates_react/backend/api/bootstrap.php` |
| `react-admin/dist/` *(full folder)* | `/public_html/plates_react/react-admin/dist/` |
| `uploads/plate/*.gif|jpg|png` *(new images)* | `/public_html/plates_react/uploads/plate/` |

Build the React app before deploying:
```powershell
cd "c:\wamp64\www\plates_react\react-admin"
npm run build
```

### Run the import on production
Repeat Steps 6–9 using the production admin URL.  
The same CSV file works — the importer skips any plates that already exist.

---

## Notes & Tips

### Series names (CA)
The converter maps CA plate variants to these series in the DB:

| CSV suffix | DB series name |
|---|---|
| `Block` | `CA02-White/Blue-Passenger-1987` |
| `Script` | `CA01-Script-2001` |
| `Sun` | `CA03-Sunset-Passenger-1982` |
| `Blue + Gold` | `CA04-Blue/Gold-Passenger-1970` |
| `Black + Gold` | `CA05-Black-Gold-Passenger-1963` |
| *(anything else)* | `CA06-Specialty-2001` *(auto-created if missing)* |

For other states you'll need to add a `XX_SERIES_MAP` block in
`convert_plates_csv.py` similar to the CA one, or leave `series_name` blank
and the importer will accept it.

### Rate limiting
The import endpoint allows **20 imports per hour** per admin user.  
If you hit the limit (429 error), wait an hour or delete the rate-limit file:
```
backend/logs/rate_limits/<hash>.json
```

### Re-running the CSV is safe
The importer checks for duplicates by `(name, region_id)` before every insert.
Plates that already exist are either skipped or get their image linked — they
are **never** double-inserted.

### Image file naming convention
Files must be lowercase kebab-case with the state prefix:
```
ca-amateur-radio-call-letters-block.gif
md-collegiate-umd-terrapins.gif
```
The Python converter produces correct names automatically.

### GIF transparency in thumbnails
PHP GD preserves GIF transparency.  PNG images with alpha channels are also
handled correctly (GD alpha-blending is disabled before resampling).

### Categories not inferred correctly
If the converter assigns `Standard` to a plate that should be in another
category, open the CSV and fix that row's `category_name` cell before
importing.  You can also update the `CATEGORY_RULES` list in
`convert_plates_csv.py` for future runs.

---

## Quick-Reference Checklist

```
[ ] 1. Download / locate raw source CSV
[ ] 2. Run convert_plates_csv.py  (--state XX  --download-images …)
[ ] 3. Fill year_introduced / year_discontinued with ChatGPT
[ ] 4. Copy images to  uploads/plate/
[ ] 5. Verify region + categories exist in DB
[ ] 6. Admin UI → CSV Bulk Import → Dry Run
[ ] 7. Fix any errors in CSV and repeat dry run until clean
[ ] 8. Commit import (inserts plates + links images)
[ ] 9. Spot-check results in the plate list
[PROD] Build react-admin  (npm run build)
[PROD] FTP files: import-csv.php, bootstrap.php, dist/, images
[PROD] Repeat steps 6–9 on production URL
```
