#!/usr/bin/env python3
"""
import_plates_from_images.py
============================
Bulk-creates plate records in platetag_api from a folder of plate images.
Designed for TN (region 43), CO (region 6), and FL (region 10) specialty-plate image sets.

Infers: plate name, slug, category_id, vehicle_class, series_id
based on filename conventions used in the TN and CO image libraries.

Filename conventions:
  TN:  tn-{descriptive-name}-{category-suffix}.jpg
         e.g. tn-desert-storm-veteran-military-memorial.jpg
  CO:  co-{descriptive-name}[-motorcycle|-passenger][-pwd].jpg
         e.g. co-bronze-star-motorcycle-pwd.jpg

Usage — DRY RUN (no writes, shows preview table):
  python tools/import_plates_from_images.py tn
  python tools/import_plates_from_images.py co
  python tools/import_plates_from_images.py fl

Usage — EXECUTE (copy images + insert DB records):
  python tools/import_plates_from_images.py tn --execute
  python tools/import_plates_from_images.py co --execute
  python tools/import_plates_from_images.py fl --execute

Options:
  --min-confidence N   Minimum confidence % to assign a field (default: 70)
  --execute            Actually copy images and insert records
  --folder PATH        Override the default image folder

─────────────────────────────────────────────────────────────────
PLATE NAME CONVENTIONS  (applies to all parser NAME_OVERRIDES)
─────────────────────────────────────────────────────────────────
Abbreviations — no periods:
  US  not U.S.     Jr  not Jr.     NCAA  not N.C.A.A.
  VFW, VFD, ALS, NASCAR — all caps, no periods, no to_title() mangling

Abbreviations — shorten where readable:
  Assn  not Association

Corporate suffixes — omit:
  "XYZ Foundation"  not "XYZ Foundation, Inc."

Descriptors — use  ` - ` separator, never parentheses:
  NC - Motorcycle   not  NC - (Motorcycle)
  NC - v1           not  NC - (V1)
  NC - Disabled     not  NC - (Disabled)

Multi-part qualifier segments — dash-separate each part:
  Standard Issue - 2009 - First In Flight   not "Standard Issue 2009 First In Flight"
  Dale Earnhardt - Hall of Fame             not "Dale Earnhardt Hall of Fame"
  NASCAR - Hall of Fame                     not "NASCAR Hall of Fame"

Acronyms that ARE the plate name — keep in parens (exception):
  VFW, AERO, etc. — only when the acronym itself is the official plate title
─────────────────────────────────────────────────────────────────
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── MySQL connection ──────────────────────────────────────────────────────────
MYSQL_BIN = r"C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe"
DB_HOST   = "127.0.0.1"
DB_PORT   = "3306"
DB_USER   = "root"
DB_PASS   = "4rfv$RFV"
DB_NAME   = "platetag_api"

# ── Image destination ─────────────────────────────────────────────────────────
IMG_DEST = r"C:\wamp64\www\platetag-api\storage\app\public\plates"

# ── TN config ─────────────────────────────────────────────────────────────────
TN_FOLDER         = r"P:\Larry Doc\Plates\assets\images\tn\tn-to-be-uploaded"
TN_DEFAULT_SERIES = {'id': 621, 'conf': 72}   # Tennessee 2023 Specialty

# Specific standard-issue series matched by stem (filename without .jpg)
TN_SERIES_MAP = {
    'tn-standard-issue-1994-bicentennial':          {'id': 641, 'conf': 95},
    'tn-2000-standard-issue-sounds-good-to-me':     {'id': 642, 'conf': 95},
    'tn-2006-standard-issue-tnvacation-dot-com':    {'id': 622, 'conf': 65},  # no exact match; closest is 2011 Green Hills
    'tn-standard-issue-2022-in-god-we-trust':       {'id': 636, 'conf': 82},
    'tn-standard-issue-2022-tnvacation':            {'id': 636, 'conf': 95},
    'tn-standard-issue-2023-darkblue-ingodwetrust': {'id': 637, 'conf': 95},
    'tn-standard-issue-2023-darkblue':              {'id': 637, 'conf': 95},
}

# ── CO config ─────────────────────────────────────────────────────────────────
CO_FOLDER         = r"P:\Larry Doc\Plates\assets\images\co\CO-Specialty\co-to-be uploaded"
CO_DEFAULT_SERIES = {'id': 620, 'conf': 88}   # Colorado Specialty 2018

# ── FL config ─────────────────────────────────────────────────────────────────
# Source: 5 subfolders under fl-specialty; all plates → series 643, region 10
FL_FOLDER         = r"P:\Larry Doc\Plates\assets\images\fl\fl-specialty"
FL_DEFAULT_SERIES = {'id': 643, 'conf': 95}   # Florida Specialty

# ── OR config ─────────────────────────────────────────────────────────────────
# Source: single flat folder; all plates → series 649 (Oregon Specialty), region 38
OR_FOLDER         = r"C:\Users\lmaje\OneDrive\Desktop\PlateTag-App-Screenshots\plate images\or\or-mil"
OR_DEFAULT_SERIES = {'id': 649, 'conf': 95}   # Oregon Specialty

# ── KY config ─────────────────────────────────────────────────────────────────
# Source: 6 subfolders; all plates → series 651 (Kentucky Specialty), region 18
KY_FOLDER         = r"C:\Users\lmaje\OneDrive\Desktop\PlateTag-App-Screenshots\plate images\ky"
KY_DEFAULT_SERIES = {'id': 651, 'conf': 95}   # Kentucky Specialty

# ── WA config ─────────────────────────────────────────────────────────────────
WA_FOLDER              = r"P:\Larry Doc\Plates\assets\images\wa"
WA_SPECIALTY_SERIES    = {'id': 653, 'conf': 95}   # Washington Specialty
WA_STD_ISSUE_SERIES    = {'id': 654, 'conf': 95}   # Washington Standard Issue

# ── AB config ─────────────────────────────────────────────────────────────────
# Source: flat folder (no subfolders), all .jpg, region = Alberta
AB_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ab"
AB_STD_ISSUE_SERIES = {'id': 655, 'conf': 95}   # Alberta - Standard Issue
AB_SPECIALTY_SERIES = {'id': 656, 'conf': 95}   # Alberta - Specialty

# ── AK config ─────────────────────────────────────────────────────────────────
# Source: 5 subfolders; no separate non-passenger series → fold into Specialty
AK_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ak"
AK_STD_ISSUE_SERIES = {'id': 657, 'conf': 95}   # Alaska - Standard Issue - Multiple Options
AK_SPECIALTY_SERIES = {'id': 658, 'conf': 95}   # Alaska - Specialty

# ── AL config ─────────────────────────────────────────────────────────────────
# Source: 7 subfolders; non-passenger folds into Specialty series
AL_FOLDER           = r"P:\Larry Doc\Plates\assets\images\al"
AL_SPECIALTY_SERIES = {'id': 663, 'conf': 95}   # Alabama - Specialty
# Standard-issue series selected by year detected in filename
AL_STD_ISSUE_SERIES = {
    '2022': {'id': 659, 'conf': 95},   # Alabama - 2022 - Beach
    '2014': {'id': 660, 'conf': 95},   # Alabama - 2014 - Pond
    '2009': {'id': 661, 'conf': 95},   # Alabama - 2009 - Sweet Home
    '2002': {'id': 662, 'conf': 95},   # Alabama - 2002 - Stars
}
AL_STD_ISSUE_DEFAULT = {'id': 659, 'conf': 85}   # fallback: newest (2022 Beach)

# ── AR config ─────────────────────────────────────────────────────────────────
# Source: 8 subfolders; dedicated non-passenger series (668)
AR_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ar"
AR_SPECIALTY_SERIES = {'id': 669, 'conf': 95}   # Arkansas - Specialty
AR_NP_SERIES        = {'id': 668, 'conf': 95}   # Arkansas - Non-Passenger
# Standard-issue series keyed by the START year of each era
AR_STD_ISSUE_SERIES = {
    '2006': {'id': 664, 'conf': 95},   # Arkansas - 2006 – Diamond
    '1996': {'id': 665, 'conf': 95},   # Arkansas - 1996 - White - Natural State
    '1988': {'id': 666, 'conf': 95},   # Arkansas - 1988 - White-Red
    '1978': {'id': 667, 'conf': 95},   # Arkansas - 1978 - Land of Opportunity
}
AR_STD_ISSUE_DEFAULT = {'id': 664, 'conf': 85}  # fallback: newest (2006 Diamond)

# ── AZ config ─────────────────────────────────────────────────────────────────
# Source: 6 subfolders; dedicated non-passenger series (671)
# 1980 series also covers pre-1980 plates and all classic/hot-rod plates
AZ_FOLDER           = r"P:\Larry Doc\Plates\assets\images\az"
AZ_SPECIALTY_SERIES = {'id': 670, 'conf': 95}   # Arizona - Specialty
AZ_NP_SERIES        = {'id': 671, 'conf': 95}   # Arizona - Non-Passenger
AZ_STD_ISSUE_SERIES = {
    '2008': {'id': 672, 'conf': 95},   # Arizona - 2008 - Grand Canyon State - Screened
    '1996': {'id': 673, 'conf': 95},   # Arizona - 1996 - Grand Canyon State - Embossed
    '1980': {'id': 674, 'conf': 95},   # Arizona - 1980 - Red (pre-1980 + classic/hot-rod)
}
AZ_STD_ISSUE_DEFAULT = {'id': 672, 'conf': 85}   # fallback: newest (2008 Screened) ────────────────────────────

# ── BC config ─────────────────────────────────────────────────────────────────
BC_FOLDER           = r"P:\Larry Doc\Plates\assets\images\bc"
BC_STD_ISSUE_SERIES = {'id': 676, 'conf': 95}    # British Columbia - Standard Issue
BC_SPECIALTY_SERIES = {'id': 677, 'conf': 95}    # British Columbia - Specialty
BC_NP_SERIES        = {'id': 678, 'conf': 95}    # British Columbia - Non-Passenger

# ── CT config ─────────────────────────────────────────────────────────────────
CT_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ct"
CT_2000_SERIES      = {'id': 679, 'conf': 95}    # Connecticut - 2000 Series (default)
CT_1987_SERIES      = {'id': 680, 'conf': 95}    # Connecticut - 1987 Series

# ── DC config ─────────────────────────────────────────────────────────────────
DC_FOLDER           = r"P:\Larry Doc\Plates\assets\images\dc"
DC_SERIES           = {'id': 681, 'conf': 95}    # Washington, D.C. (all plates)

# ── DE config ─────────────────────────────────────────────────────────────────
DE_FOLDER           = r"P:\Larry Doc\Plates\assets\images\de"
DE_SERIES           = {'id': 682, 'conf': 95}    # Delaware - all plates (proofread will reassign 683/684)

# ── GA config ─────────────────────────────────────────────────────────────────
GA_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ga"
GA_SERIES_STANDARD  = {'id': 685, 'conf': 95}   # Georgia - 2012 - Peach State
GA_SERIES_PRESTIGE  = {'id': 686, 'conf': 95}   # Georgia - 2012 - Prestige (Alternative)
GA_SERIES_SPECIALTY = {'id': 687, 'conf': 95}   # Georgia - Specialty
GA_SERIES_NON_PASS  = {'id': 688, 'conf': 95}   # Georgia - Non-Passenger

# ── IA config ─────────────────────────────────────────────────────────────────
IA_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ia"
IA_SERIES_STANDARD  = {'id': 689, 'conf': 95}   # Iowa - 2018 - Standard Issue - County Name
IA_SERIES_SPECIALTY = {'id': 690, 'conf': 95}   # Iowa - Specialty

# ── IN config ─────────────────────────────────────────────────────────────────
# Source: 9 subfolders; 5 year-based standard-issue series; specialty (701); non-passenger (702)
IN_FOLDER           = r"P:\Larry Doc\Plates\assets\images\in"
IN_STD_2017_SERIES  = {'id': 696, 'conf': 95}   # Indiana - 2017 - Standard Issue - Covered Bridge
IN_STD_2013_SERIES  = {'id': 697, 'conf': 95}   # Indiana - 2013 - Standard Issue - Bicentennial
IN_STD_2008_SERIES  = {'id': 698, 'conf': 95}   # Indiana - 2008 - Standard Issue - Blue
IN_STD_2003_SERIES  = {'id': 699, 'conf': 95}   # Indiana - 2003 - Standard Issue - Farm
IN_STD_1998_SERIES  = {'id': 700, 'conf': 95}   # Indiana - 1998 - Standard Issue - Crossroads
IN_SPECIALTY_SERIES = {'id': 701, 'conf': 95}   # Indiana - Specialty
IN_NON_PASS_SERIES  = {'id': 702, 'conf': 95}   # Indiana - Non-Passenger

# ── ID config ─────────────────────────────────────────────────────────────────
ID_FOLDER       = r"P:\Larry Doc\Plates\assets\images\id"
ID_SERIES_SCENIC = {'id': 691, 'conf': 95}  # Idaho - 1991 - Standard Issue - Scenic (used for all plates)
# Series 692 (Idaho - Specialty) will be assigned manually in Filament

# ── KS config ─────────────────────────────────────────────────────────────────
# Source: 8 subfolders; 5 year/design-based standard-issue series; specialty (708); non-passenger (709)
KS_FOLDER            = r"P:\Larry Doc\Plates\assets\images\ks"
KS_STD_2007_SERIES   = {'id': 703, 'conf': 95}  # Kansas - Standard Issue - 2007 - Astra - Embossed
KS_STD_2019_SERIES   = {'id': 704, 'conf': 95}  # Kansas - Standard Issue - 2019 - Astra - Screened
KS_PERS_2020_SERIES  = {'id': 705, 'conf': 95}  # Kansas - Personalized Issue - 2020 - Powering The Future
KS_STD_2025_SERIES   = {'id': 706, 'conf': 95}  # Kansas - Standard Issue - 2025 - To The Stars
KS_PERS_2025_SERIES  = {'id': 707, 'conf': 95}  # Kansas - Personalized Issue - 2025 - Flint Hills Sunrise
KS_SPECIALTY_SERIES  = {'id': 708, 'conf': 95}  # Kansas - Specialty
KS_NON_PASS_SERIES   = {'id': 709, 'conf': 95}  # Kansas - Non-Passenger

# ── LA config ────────────────────────────────────────────────────────────────
LA_FOLDER           = r"P:\Larry Doc\Plates\assets\images\la"
LA_STD_2025_SERIES  = {'id': 710, 'conf': 95}  # Louisiana - Standard Issue - 2025 - America 250
LA_STD_2005_SERIES  = {'id': 711, 'conf': 95}  # Louisiana - Standard Issue - 2005 - Pelican
LA_NON_PASS_SERIES  = {'id': 712, 'conf': 95}  # Louisiana - Non-Passenger
LA_SPECIALTY_SERIES = {'id': 713, 'conf': 95}  # Louisiana - Specialty

# ── MA config ────────────────────────────────────────────────────────────────
MA_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ma"
MA_STD_SERIES       = {'id': 714, 'conf': 95}  # Massachusetts - Standard Issue - 1993 - Spirit
MA_SPECIALTY_SERIES = {'id': 715, 'conf': 95}  # Massachusetts - Specialty
MA_NON_PASS_SERIES  = {'id': 716, 'conf': 95}  # Massachusetts - Non-Passenger

# ── MB config ────────────────────────────────────────────────────────────────
MB_FOLDER           = r"P:\Larry Doc\Plates\assets\images\mb"
MB_STD_SERIES       = {'id': 717, 'conf': 95}  # Manitoba - Standard Issue - 1997
MB_SPECIALTY_SERIES = {'id': 718, 'conf': 95}  # Manitoba - Specialty (catch-all incl. non-passenger)

# ── MD config ────────────────────────────────────────────────────────────────
MD_FOLDER           = r"P:\Larry Doc\Plates\assets\images\md"
MD_STD_2016_SERIES  = {'id': 719, 'conf': 95}  # Maryland - Standard Issue - 2016 - Flag
MD_STD_1986_SERIES  = {'id': 720, 'conf': 95}  # Maryland - Standard Issue - 1986 - Shield
MD_SPECIALTY_SERIES = {'id': 721, 'conf': 95}  # Maryland - Specialty

# ── ME config ────────────────────────────────────────────────────────────────
ME_FOLDER           = r"P:\Larry Doc\Plates\assets\images\me"
ME_STD_1999_SERIES  = {'id': 722, 'conf': 95}  # Maine - Standard Issue 1999 Chickadee
ME_STD_2025_SERIES  = {'id': 723, 'conf': 95}  # Maine - Standard Issue 2025 White
ME_SPECIALTY_SERIES = {'id': 724, 'conf': 95}  # Maine - Specialty
ME_VETERAN_SERIES   = {'id': 725, 'conf': 95}  # Maine - Veteran

# ── IL config ────────────────────────────────────────────────────────────────
IL_FOLDER           = r"P:\Larry Doc\Plates\assets\images\il"
IL_STD_SERIES       = {'id': 693, 'conf': 95}  # Illinois - 2017 Standard Issue Land of Lincoln
IL_NP_SERIES        = {'id': 694, 'conf': 95}  # Illinois - Non-Passenger
IL_SPECIALTY_SERIES = {'id': 695, 'conf': 95}  # Illinois - Specialty
IL_VETERAN_SERIES   = {'id': 727, 'conf': 95}  # Illinois - Veteran and Military

# ── MI config ────────────────────────────────────────────────────────────────
MI_FOLDER           = r"P:\Larry Doc\Plates\assets\images\mi"
MI_STD_SERIES       = {'id': 726, 'conf': 95}  # Michigan - Standard Issue 2013 Pure Michigan
MI_ALT_SERIES       = {'id': 728, 'conf': 95}  # Michigan - Standard Issue Alternatives (reissues)
MI_NP_SERIES        = {'id': 729, 'conf': 95}  # Michigan - Non-Passenger
MI_VETERAN_SERIES   = {'id': 730, 'conf': 95}  # Michigan - Veteran and Military
MI_SPECIALTY_SERIES = {'id': 731, 'conf': 95}  # Michigan - Specialty

# ── MN config ────────────────────────────────────────────────────────────────
MN_FOLDER           = r"P:\Larry Doc\Plates\assets\images\mn"
MN_STD_SERIES       = {'id': 732, 'conf': 95}  # Minnesota - Standard Issue 1987 Explore
MN_WHITE_SERIES     = {'id': 733, 'conf': 95}  # Minnesota - White (Standard, Government and Commercial)
MN_SPECIALTY_SERIES = {'id': 734, 'conf': 95}  # Minnesota - Specialty
MN_VETERAN_SERIES   = {'id': 735, 'conf': 95}  # Minnesota - Veteran

# ── MO config ────────────────────────────────────────────────────────────────
MO_FOLDER           = r"P:\Larry Doc\Plates\assets\images\mo"
MO_STD_2018_SERIES  = {'id': 736, 'conf': 95}  # Missouri - Standard Issue 2018 Bicentennial
MO_VETERAN_SERIES   = {'id': 737, 'conf': 95}  # Missouri - Military and Veteran
MO_SPECIALTY_SERIES = {'id': 738, 'conf': 95}  # Missouri - Specialty
MO_STD_2008_SERIES  = {'id': 739, 'conf': 95}  # Missouri - Standard Issue 2008 Bluebird
MO_STD_1997_SERIES  = {'id': 740, 'conf': 95}  # Missouri - Standard Issue 1997 Show-Me
MO_CIVIC_SERIES     = {'id': 741, 'conf': 95}  # Missouri - Civic and Government

# ── MS config ────────────────────────────────────────────────────────────────
MS_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ms"
MS_STD_2019_SERIES  = {'id': 742, 'conf': 95}  # Mississippi - Standard Issue 2019 Gold Seal
MS_STD_2024_SERIES  = {'id': 743, 'conf': 95}  # Mississippi - Standard Issue 2024 Magnolia
MS_BLACKOUT_SERIES  = {'id': 744, 'conf': 95}  # Mississippi - Alternative Issue 2022 Blackout
MS_VETERAN_SERIES   = {'id': 745, 'conf': 95}  # Mississippi - Veteran and Military
MS_NONPASS_SERIES   = {'id': 746, 'conf': 95}  # Mississippi - Non-Passenger and Government
MS_SPECIALTY_SERIES = {'id': 747, 'conf': 95}  # Mississippi - Specialty

# ── MT config ────────────────────────────────────────────────────────────────
MT_FOLDER           = r"P:\Larry Doc\Plates\assets\images\mt"
MT_VETERAN_SERIES   = {'id': 748, 'conf': 95}  # Montana - Military and Veteran
MT_STD_2010_SERIES  = {'id': 749, 'conf': 95}  # Montana - Standard Issue 2010 Blue
MT_STD_2006_SERIES  = {'id': 750, 'conf': 95}  # Montana - Standard Issue 2006 Gold Font
MT_STD_2000_SERIES  = {'id': 751, 'conf': 95}  # Montana - Standard Issue 2000 Blue Font
MT_STD_1991_SERIES  = {'id': 752, 'conf': 95}  # Montana - Standard Issue 1991 White Font
MT_STD_1989_SERIES  = {'id': 753, 'conf': 95}  # Montana - Standard Issue 1989 Centennial
MT_SPECIALTY_SERIES = {'id': 754, 'conf': 95}  # Montana - Specialty

# ── NC config ────────────────────────────────────────────────────────────────
NC_FOLDER           = r"P:\Larry Doc\Plates\assets\images\nc"
NC_STD_SERIES       = {'id': 756, 'conf': 95}  # North Carolina - Standard Issue 1982 - First In Flight
NC_NON_PASS_SERIES  = {'id': 757, 'conf': 95}  # North Carolina - Non-Passenger
NC_SPECIALTY_SERIES = {'id': 758, 'conf': 95}  # North Carolina - Specialty

# ── ND config ────────────────────────────────────────────────────────────────
ND_FOLDER           = r"P:\Larry Doc\Plates\assets\images\nd"
ND_STD_SERIES       = {'id': 759, 'conf': 95}  # North Dakota - Standard Issue - 2015 - Legendary
ND_VINTAGE_SERIES   = {'id': 760, 'conf': 95}  # North Dakota - Vintage
ND_BLACKOUT_SERIES  = {'id': 761, 'conf': 95}  # North Dakota - Alternative Issue - 2025 - Blackout
ND_SPECIALTY_SERIES = {'id': 762, 'conf': 95}  # North Dakota - Specialty

# ── NE config ────────────────────────────────────────────────────────────────
NE_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ne"
NE_STD_2023_SERIES  = {'id': 763, 'conf': 95}  # Nebraska - Standard Issue - 2023 - Genius
NE_STD_2017_SERIES  = {'id': 764, 'conf': 95}  # Nebraska - Standard Issue - 2017 - Sesquicentennial
NE_STD_2011_SERIES  = {'id': 765, 'conf': 95}  # Nebraska - Standard Issue - 2011 - Meadowlark
NE_STD_2005_SERIES  = {'id': 766, 'conf': 95}  # Nebraska - Standard Issue - 2005 - Conestoga
NE_STD_2002_SERIES  = {'id': 767, 'conf': 95}  # Nebraska - Standard Issue - 2002 - Prairie River
NE_SPECIALTY_SERIES = {'id': 768, 'conf': 95}  # Nebraska - Specialty
NE_MILITARY_SERIES  = {'id': 769, 'conf': 95}  # Nebraska - Military and Veteran
NE_NON_PASS_SERIES  = {'id': 770, 'conf': 95}  # Nebraska - Non-passenger and Governmental

# ── NH config ────────────────────────────────────────────────────────────────
NH_FOLDER           = r"P:\Larry Doc\Plates\assets\images\nh"
NH_STD_1999_SERIES  = {'id': 771, 'conf': 95}  # New Hampshire - Standard Issue - 1999 - Live Free or Die
NH_STD_2026_SERIES  = {'id': 772, 'conf': 95}  # New Hampshire - Standard Issue - 2026 - Bicentennial
NH_NON_PASS_SERIES  = {'id': 773, 'conf': 95}  # New Hampshire - Non-Passenger and Government
NH_SPECIALTY_SERIES = {'id': 774, 'conf': 95}  # New Hampshire - Specialty

# ── NJ config ────────────────────────────────────────────────────────────────
NJ_FOLDER           = r"P:\Larry Doc\Plates\assets\images\nj"
NJ_STD_SERIES       = {'id': 775, 'conf': 95}  # New Jersey - Standard Issue - 1992
NJ_NON_PASS_SERIES  = {'id': 776, 'conf': 95}  # New Jersey - Non Passenger
NJ_SPECIALTY_SERIES = {'id': 777, 'conf': 95}  # New Jersey - Specialty
NJ_MIL_SERIES       = {'id': 778, 'conf': 95}  # New Jersey - Military and Veteran

# ── NM config ────────────────────────────────────────────────────────────────
NM_FOLDER           = r"P:\Larry Doc\Plates\assets\images\nm"
NM_STD_SERIES       = {'id': 779, 'conf': 95}  # New Mexico - Standard Issue - 1990 - Yellow
NM_ALT_TURQ_SERIES  = {'id': 780, 'conf': 95}  # New Mexico - Alternative Issue - 2016 - Turquoise
NM_ALT_CENT_SERIES  = {'id': 781, 'conf': 95}  # New Mexico - Alternative Issue - 2010 - Centennial
NM_ALT_CHIL_SERIES  = {'id': 782, 'conf': 95}  # New Mexico - Alternative Issue - 2017 - Chilies
NM_MIL_SERIES       = {'id': 783, 'conf': 95}  # New Mexico - Veteran and Military
NM_NON_PASS_SERIES  = {'id': 784, 'conf': 95}  # New Mexico - Non-Passenger and Government
NM_SPECIALTY_SERIES = {'id': 785, 'conf': 95}  # New Mexico - Specialty
NM_ALT_BALL_SERIES  = {'id': 786, 'conf': 95}  # New Mexico - Alternative Issue - 1999 - Balloon

# ── NT config (single plate, manually created in Filament) ────────────────────────────
NT_STD_SERIES       = {'id': 787, 'conf': 95}  # Northwest Territories - Standard Issue - 2010 - Spectacular

# ── NV config ────────────────────────────────────────────────────────────────
NV_FOLDER           = r"P:\Larry Doc\Plates\assets\images\nv"
NV_STD_2016_SERIES  = {'id': 788, 'conf': 95}  # Nevada - Standard Issue - 2016 - Home
NV_STD_2001_SERIES  = {'id': 789, 'conf': 95}  # Nevada - Standard Issue - 2001 - Sunset
NV_STD_1983_SERIES  = {'id': 790, 'conf': 95}  # Nevada - Standard Issue - 1983 - Big Horn Sheep
NV_STD_1969_SERIES  = {'id': 791, 'conf': 95}  # Nevada - Standard Issue - 1969 - Blue
NV_ALT_2024_SERIES  = {'id': 792, 'conf': 95}  # Nevada - Alternative Issue - 2024 - 1969 Blue Reissue
NV_MIL_SERIES       = {'id': 793, 'conf': 95}  # Nevada - Military and Veteran
NV_SPECIALTY_SERIES = {'id': 794, 'conf': 95}  # Nevada - Specialty

# ── NY config ─────────────────────────────────────────────────────────────────
NY_FOLDER              = r"P:\Larry Doc\Plates\assets\images\ny"
NY_STD_2020_SERIES     = {'id': 624, 'conf': 95}  # New York - Standard Issue - 2020 - Excelsior
NY_SPECIALTY_SERIES    = {'id': 625, 'conf': 95}  # New York - Specialty - Excelsior
NY_STD_2010_SERIES     = {'id': 626, 'conf': 95}  # New York - Standard Issue - 2010 - Empire Gold
NY_STD_2001_SERIES     = {'id': 796, 'conf': 95}  # New York - Standard Issue - 2001 - Empire State
NY_NP_GOLD_SERIES      = {'id': 797, 'conf': 95}  # New York - Non-passenger and Government - 2010 - Empire Gold
NY_NP_STATE_SERIES     = {'id': 798, 'conf': 95}  # New York - Non-passenger and Government - 2001 - Empire State
NY_NP_EXCELSIOR_SERIES = {'id': 799, 'conf': 95}  # New York - Non-passenger and Government - 2020 - Excelsior
NY_STD_1986_SERIES     = {'id': 800, 'conf': 95}  # New York - Standard Issue - 1986 - Statue of Liberty

# ── OH config ─────────────────────────────────────────────────────────────────
OH_FOLDER           = r"P:\Larry Doc\Plates\assets\images\oh"
OH_STD_2021_SERIES  = {'id': 801, 'conf': 95}  # Ohio - Standard Issue - 2021 - Sunrise
OH_STD_2013_SERIES  = {'id': 802, 'conf': 95}  # Ohio - Standard Issue - 2013 - Pride
OH_STD_2008_SERIES  = {'id': 803, 'conf': 95}  # Ohio - Standard Issue - 2008 - Beautiful
OH_SPECIALTY_SERIES = {'id': 804, 'conf': 95}  # Ohio - Specialty - Sunrise
OH_NP_SERIES        = {'id': 805, 'conf': 95}  # Ohio - Non-passenger and Government

# ── OK config ─────────────────────────────────────────────────────────────────
OK_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ok"
OK_STD_2024_SERIES  = {'id': 806, 'conf': 95}  # Oklahoma - Standard Issue - 2024 - Imagine That
OK_STD_2017_SERIES  = {'id': 807, 'conf': 95}  # Oklahoma - Standard Issue - 2017 - Scissortail
OK_SPECIALTY_SERIES = {'id': 808, 'conf': 95}  # Oklahoma - Specialty
OK_MIL_SERIES       = {'id': 809, 'conf': 95}  # Oklahoma - Military and Veteran
OK_NP_SERIES        = {'id': 810, 'conf': 95}  # Oklahoma - Non-passenger and Governmental

# ── ON config ─────────────────────────────────────────────────────────────────
ON_FOLDER           = r"P:\Larry Doc\Plates\assets\images\on"
ON_STD_SERIES       = {'id': 811, 'conf': 95}  # Ontario - Standard Issue - 1995 - Yours to Discover
ON_SPECIALTY_SERIES = {'id': 812, 'conf': 95}  # Ontario - Specialty

# ── RI config ─────────────────────────────────────────────────────────────────
RI_FOLDER           = r"P:\Larry Doc\Plates\assets\images\ri"
RI_STD_OCEAN_SERIES = {'id': 814, 'conf': 95}  # Rhode Island - Standard Issue - 2023 - Ocean
RI_ALT_SAIL_SERIES  = {'id': 815, 'conf': 95}  # Rhode Island - Alternative Issue - 1992 - Sailboat
RI_ALT_SHARK_SERIES = {'id': 816, 'conf': 95}  # Rhode Island - Alternative Issue - 2023 - Shark
RI_SPECIALTY_SERIES = {'id': 817, 'conf': 95}  # Rhode Island - Specialty
RI_VET_SERIES       = {'id': 818, 'conf': 95}  # Rhode Island - Veteran

# ── SC config ─────────────────────────────────────────────────────────────────
SC_FOLDER           = r"P:\Larry Doc\Plates\assets\images\sc"
SC_STD_SERIES       = {'id': 819, 'conf': 95}  # South Carolina - Standard Issue - 2016 - While I Breathe I Hope
SC_SPECIALTY_SERIES = {'id': 820, 'conf': 95}  # South Carolina - Specialty
SC_PERS_SERIES      = {'id': 821, 'conf': 95}  # South Carolina - Personalized

# ── SD config ─────────────────────────────────────────────────────────────────
SD_FOLDER           = r"P:\Larry Doc\Plates\assets\images\sd"
SD_STD_SERIES       = {'id': 822, 'conf': 95}  # South Dakota - Standard Issue - 2006 - Great Faces
SD_SPECIALTY_SERIES = {'id': 823, 'conf': 95}  # South Dakota - Specialty 2016
SD_WHITE_SERIES     = {'id': 824, 'conf': 95}  # South Dakota - Specialty White

# ── SK config ─────────────────────────────────────────────────────────────────
SK_FOLDER  = r"P:\Larry Doc\Plates\assets\images\sk"
SK_SERIES  = {'id': 825, 'conf': 95}  # Saskatchewan - All plates (single series)

# ── PE config ─────────────────────────────────────────────────────────────────────────────────────
PE_FOLDER      = r"P:\Larry Doc\Plates\assets\images\pe"
PE_STD_SERIES  = {'id': 829, 'conf': 95}  # PEI - Standard Issue
PE_ALT_SERIES  = {'id': 830, 'conf': 95}  # PEI - Alt Issue (green/white + 2 yellow dealer)

# ── UT config ─────────────────────────────────────────────────────────────────────────────────────
UT_FOLDER          = r"P:\Larry Doc\Plates\assets\images\ut"
UT_ALT_SKIER       = {'id': 833, 'conf': 95}  # Utah - Alternative Issue - Skier (2007+)
UT_ALT_ARCHES      = {'id': 834, 'conf': 95}  # Utah - Alternative Issue - Arches (2007+)
UT_STD_CENTENNIAL  = {'id': 835, 'conf': 95}  # Utah - Standard Issue - Centennial (1992-2007)
UT_STD_1985        = {'id': 836, 'conf': 95}  # UT - Standard Issue - 1985 - Skier
UT_STD_1973        = {'id': 837, 'conf': 95}  # Utah - Standard Issue - 1973 - UTAH
UT_SPECIALTY       = {'id': 838, 'conf': 95}  # Utah - Specialty (2017+)

# ── VT config ─────────────────────────────────────────────────────────────────────────────────────
VT_FOLDER      = r"P:\Larry Doc\Plates\assets\images\vt"
VT_STD_SERIES  = {'id': 839, 'conf': 95}  # Vermont - Standard Issue
VT_SPECIALTY   = {'id': 840, 'conf': 95}  # Vermont - Specialty

# ── WI config ─────────────────────────────────────────────────────────────────────────────────────
WI_FOLDER          = r"P:\Larry Doc\Plates\assets\images\wi"

# ── WV config ─────────────────────────────────────────────────────────────────────────────────────
WV_FOLDER      = r"P:\Larry Doc\Plates\assets\images\wv"
WV_STD_SERIES  = {'id': 849, 'conf': 95}  # West Virginia - Standard Issue - 1995 - Wild, Wonderful
WV_SPECIALTY   = {'id': 850, 'conf': 90}  # West Virginia - Specialty (catch-all)

# ── TX config ─────────────────────────────────────────────────────────────────────────────────────
TX_FOLDER        = r"P:\Larry Doc\Plates\assets\images\tx"
TX_SCHOOLS       = {'id': 857, 'conf': 95}  # Texas - Schools
TX_ALTERNATIVES  = {'id': 858, 'conf': 95}  # Texas - Alternatives (vendor vanity)
TX_SPORTS        = {'id': 859, 'conf': 95}  # Texas - Sports
TX_STD_1992      = {'id': 860, 'conf': 95}  # Texas - Standard Issue - 1992 - Lone Star State
TX_STD_2000      = {'id': 861, 'conf': 95}  # Texas - Standard Issue - 2000 - Space Shuttle
TX_STD_2009      = {'id': 863, 'conf': 95}  # Texas - Standard Issue - 2009 - Davis Mountains
TX_STD_2012      = {'id': 864, 'conf': 95}  # Texas - Standard Issue - 2012 - White
TX_MILITARY      = {'id': 865, 'conf': 95}  # Texas - Military
TX_SPECIALTY     = {'id': 866, 'conf': 90}  # Texas - Specialty

# ── WY config ─────────────────────────────────────────────────────────────────────────────────────
WY_FOLDER       = r"P:\Larry Doc\Plates\assets\images\wy"
WY_2025_SERIES  = {'id': 851, 'conf': 95}  # Wyoming - Standard Issue - 2025 - Prestige
WY_2016_SERIES  = {'id': 852, 'conf': 95}  # Wyoming - Standard Issue - 2016 - Green River
WI_STD_SERIES      = {'id': 841, 'conf': 95}  # Wisconsin - Standard Issue - 1986 - Americas Dairyland

VA_FOLDER          = r"P:\Larry Doc\Plates\assets\images\va"
VA_STD_SERIES      = {'id': 846, 'conf': 95}  # Virginia - Standard Issue - 2014 - Virginia Is For Lovers
VA_NONPASS_SERIES  = {'id': 847, 'conf': 95}  # Virginia - Non-passenger and Government
VA_SPECIALTY       = {'id': 848, 'conf': 90}  # Virginia - Specialty (catch-all)
WI_ALT_SERIES      = {'id': 842, 'conf': 95}  # Wisconsin - Alternative Series (Retro Yellow, Blackout)
WI_NONPASS_SERIES  = {'id': 843, 'conf': 95}  # Wisconsin - Non-passenger and Governmental
WI_TRIBAL_SERIES   = {'id': 844, 'conf': 90}  # Wisconsin - Tribal Nations
WI_SPECIALTY       = {'id': 845, 'conf': 90}  # Wisconsin - Specialty (catch-all)

CAT = {
    'Standard Issue':          1,
    'School':                  2,
    'Military / Veteran':      3,
    'Dealer / Manufacturer':   4,
    'Disabled / Accessibility':5,
    'Government / Exempt':     6,
    'First Responder':         7,
    'Conservation / Environment': 8,
    'Health & Awareness':      9,
    'Sports Team':            10,
    'Arts / Culture':         11,
    'Agricultural':           12,
    'Fraternal / Civic':      13,
    'Historical / Commemorative': 14,
    'Other / Specialty':      15,
    'Radio / Amateur Radio':  16,
}

# ── TN suffix → category rules (checked longest-first; first match wins) ─────
# (suffix_string, category_id, confidence)
TN_SUFFIX_RULES = [
    ('-wildlife-animal-environment',  CAT['Conservation / Environment'],   88),
    ('-military-memorial',            CAT['Military / Veteran'],           92),
    ('-emergency-safety',             CAT['First Responder'],              92),
    ('-wildlife-animal',              CAT['Conservation / Environment'],   88),
    ('-environment-conservation',     CAT['Conservation / Environment'],   90),
    ('-clubs-organizations',          CAT['Fraternal / Civic'],            78),
    ('-fraternity-sorority',          CAT['Fraternal / Civic'],            92),
    ('-hospitals-for-children',       CAT['Health & Awareness'],           92),
    ('-hospitals',                    CAT['Health & Awareness'],           88),
    ('-for-children',                 CAT['Health & Awareness'],           78),
    ('-sports',                       CAT['Sports Team'],                  92),
    ('-collegiate',                   CAT['School'],                       92),
]

# TN name-keyword fallback rules (when no suffix matches)
# (list_of_substrings, category_id, confidence)
TN_KEYWORD_RULES = [
    (['university', 'college'],                                           CAT['School'],                    82),
    (['predators', 'titans', 'braves', 'nashville-sc', 'tennis',
      'basketball', 'football', 'baseball', 'soccer'],                   CAT['Sports Team'],               85),
    (['guard', 'military', 'veteran', 'army', 'navy', 'air-force',
      'marines', 'ranger', 'paratrooper', 'pearl-harbor'],               CAT['Military / Veteran'],        80),
    (['firefight', 'fire-', 'rescue', 'firefighter'],                    CAT['First Responder'],           75),
    (['wildlife', 'sanctuary', 'conservation', 'environment',
      'nature', 'lake', 'river', 'shoals', 'historic'],                  CAT['Conservation / Environment'], 74),
    (['fraternal', 'fraternity', 'sorority', 'order', 'lodge',
      'alpha', 'kappa', 'phi', 'sigma', 'omega', 'zeta', 'beta',
      'gamma', 'theta'],                                                  CAT['Fraternal / Civic'],         78),
    (['hospital', 'cancer', 'health', 'awareness', 'st-jude',
      'lebonheur', 'niswonger', 'vanderbilt', 'children'],               CAT['Health & Awareness'],        75),
    (['arts', 'museum', 'music', 'foundation', 'symphony',
      'theater', 'theatre', 'commission', 'tennesseans-for-the-arts'],   CAT['Arts / Culture'],            75),
    (['standard-issue'],                                                  CAT['Standard Issue'],            90),
    (['county', 'city', 'hendersonville', 'wilson', 'emergency-e-plate'],
                                                                          CAT['Government / Exempt'],       72),
]

# ── CO name-keyword → category rules ─────────────────────────────────────────
CO_KEYWORD_RULES = [
    (['air-force-cross', 'bronze-star', 'silver-star', 'medal-of-honor',
      'purple-heart', 'navy-cross', 'pearl-harbor', 'prisoner-of-war',
      'civil-air-patrol', 'paratrooper', 'combat', 'distinguished',
      'military', 'veteran', 'national-guard', 'army', 'navy',
      'air-force', 'coast-guard', 'ranger', 'special-forces',
      'legion-of-merit'],                                                 CAT['Military / Veteran'],        92),
    (['cancer', 'child-loss', 'childhood-cancer', 'breast-cancer',
      'hospital', 'health', 'awareness', 'autism', 'alzheimer',
      'down-syndrome', 'organ-donor', 'st-jude', 'niswonger'],           CAT['Health & Awareness'],        90),
    (['boy-scouts', 'girl-scouts', 'rotary', 'american-legion',
      'fraternal', 'organizations', 'elks', 'moose', 'lions',
      'veterans-of-foreign'],                                             CAT['Fraternal / Civic'],         85),
    (['scholars', 'university', 'college', 'school', 'education'],       CAT['School'],                    80),
    (['wildlife', 'conservation', 'nature', 'environment', 'outdoors',
      'hunting', 'fishing', 'elk', 'turkey', 'ducks', 'trout'],         CAT['Conservation / Environment'], 82),
    (['firefighter', 'police', 'rescue', 'ems', 'fire-'],                CAT['First Responder'],           85),
    (['sports', 'team', 'soccer', 'football', 'baseball', 'nfl'],        CAT['Sports Team'],               85),
    (['arts', 'museum', 'culture', 'music', 'theater', 'orchestra'],     CAT['Arts / Culture'],            78),
]

# ── FL lookup tables (require CAT to be defined above) ───────────────────────
# Subfolder → category (None = use FL_SPECIAL_INTEREST_RULES instead)
FL_SUBFOLDER_CATEGORIES = {
    'fl-environment':    {'cat_id': CAT['Conservation / Environment'], 'conf': 92},
    'fl-military':       {'cat_id': CAT['Military / Veteran'],         'conf': 92},
    'fl-schools':        {'cat_id': CAT['School'],                     'conf': 92},
    'fl-special-interest': None,                        # keyword-based — see below
    'fl-sports':         {'cat_id': CAT['Sports Team'],                'conf': 90},
}

# fl-special-interest keyword rules — checked in order, first match wins
# (list_of_substrings_in_core, category_id, confidence)
FL_SPECIAL_INTEREST_RULES = [
    (['law-enforcement', 'firefight', 'sheriff', 'sherif', 'k9s',
      'police', 'salutes-fire', 'fallen-law'],             CAT['First Responder'],             88),
    (['agricultural', 'agriculture', 'horse-country'],      CAT['Agricultural'],                88),
    (['freemasonry', 'scout', 'big-brothers', 'fraternal'], CAT['Fraternal / Civic'],           82),
    (['cancer', 'autism', 'breast', 'hospice', 'drug-free',
      'invest-in-child', 'kids-deserve', 'laurens-kids',
      'keep-kids', 'stop-child', 'stop-heart', 'end-breast',
      'mofitt', 'choose-life', 'bestbuddies'],              CAT['Health & Awareness'],          88),
    (['state-of-the-arts', 'imagine'],                       CAT['Arts / Culture'],              80),
    (['challenger-columbia'],                                 CAT['Historical / Commemorative'], 90),
    (['support-education'],                                   CAT['School'],                      78),
]

# ── KY lookup tables (require CAT to be defined above) ────────────────────────────────────────────────
# Subfolder → category (None = use keyword rules)
KY_SUBFOLDER_CATEGORIES = {
    'ky-military':        {'cat_id': CAT['Military / Veteran'],   'conf': 95},
    'ky-government':      {'cat_id': CAT['Government / Exempt'],  'conf': 92},
    'ky-schools':         {'cat_id': CAT['School'],               'conf': 95},
    'ky-commercial':      None,
    'ky-miscellaneous':   None,
    'ky-special-interest': None,
}

# ky-commercial keyword rules
KY_COMMERCIAL_RULES = [
    (['farm'],                                         CAT['Agricultural'],           88),
    (['dealer', 'drive-away'],                         CAT['Dealer / Manufacturer'],  90),
]
KY_COMMERCIAL_DEFAULT = (CAT['Other / Specialty'], 78)

# ky-miscellaneous keyword rules
KY_MISC_RULES = [
    (['dealer', 'drive-away'],                         CAT['Dealer / Manufacturer'],  90),
    (['historic', 'street-rod'],                       CAT['Historical / Commemorative'], 88),
]
KY_MISC_DEFAULT = (CAT['Other / Specialty'], 78)

# ky-special-interest keyword rules
KY_SPECIAL_RULES = [
    (['standard-issue'],                               CAT['Standard Issue'],          90),
    (['amateur-radio'],                                CAT['Radio / Amateur Radio'],   95),
    (['pow-never-forgotten', 'i-support-veterans',
      'support-veterans'],                             CAT['Military / Veteran'],      88),
    (['firefighter', 'fire-', 'ems-memorial',
      'emergency-management', 'cops', 'fraternal-order-of-police',
      'kentucky-cops', 'remembering-fallen'],          CAT['First Responder'],         88),
    (['alpha-kappa', 'alpha-phi', 'delta-sigma',
      'kappa-alpha', 'omega-psi', 'phi-beta', 'zeta-phi',
      'making-good-men', 'fraternal-order'],           CAT['Fraternal / Civic'],       90),
    (['cancer', 'autism', 'downs-syndrome',
      'alzheimer', 'diabetes', 'mental-health',
      'nortons', 'pikeville-medical', 'organ-eye',
      'heart-disease', 'suicide', 'choose-life',
      'curing-childhood', 'honor-kentucky-nurses',
      'i-care-about-kids', 'advocates-for-kids',
      'be-the-difference', 'fentanyl', 'spay-or-neuter'],
                                                       CAT['Health & Awareness'],      88),
    (['ducks-unlimited', 'natures-finest', 'promoting-wildlife',
      'protect-kentucky-bees', 'red-river-gorge',
      'smallmouth-bass', 'wild-turkey', 'beautify',
      'ohv4ky', 'go-wild'],                            CAT['Conservation / Environment'], 88),
    (['friends-of-ky-agriculture', 'cattlemens',
      'horse-council', 'horseswork', 'americansaddlebred',
      'nothing-without-trucking'],                     CAT['Agricultural'],            88),
    (['keeneland', 'lexington-sporting', 'ryder-cup',
      'league-of-ky-sportsmen'],                       CAT['Sports Team'],             85),
    (['kentuckians-for-the-arts', 'shaker-village',
      'bardstown'],                                    CAT['Arts / Culture'],          82),
]

# ── WA lookup tables (require CAT to be defined above) ───────────────────────
# Subfolder → (category, conf, series) — None series means keyword-determines it
WA_SUBFOLDER_CATEGORIES = {
    'wa-military':       {'cat_id': CAT['Military / Veteran'],        'conf': 95, 'series': 'specialty'},
    'wa-outdoor':        {'cat_id': CAT['Conservation / Environment'], 'conf': 90, 'series': 'specialty'},
    'wa-schools':        {'cat_id': CAT['School'],                     'conf': 95, 'series': 'specialty'},
    'wa-sports':         None,  # keyword for share-the-road outlier
    'wa-civic':          None,  # keyword-based
    'wa-standard-issue': None,  # keyword-based — splits between two series
}

# wa-sports: almost everything is Sports Team; only exception is share-the-road
WA_SPORTS_RULES = [
    (['share-the-road'],  CAT['Other / Specialty'], 78),
]
WA_SPORTS_DEFAULT = (CAT['Sports Team'], 90)

# wa-civic keyword rules — checked in order, first match wins
WA_CIVIC_RULES = [
    (['professional-firefighter', 'volunteer-firefighter',
      'law-enforcement-memorial'],                    CAT['First Responder'],             90),
    (['freemason'],                                    CAT['Fraternal / Civic'],           90),
    (['4-h', 'ffa', 'worlds-finest-apples'],           CAT['Agricultural'],                88),
    (['cancer', 'fred-hutchinson', 'keep-kids-safe',
      'prevent-veteran-suicide', 'spay-neuter'],       CAT['Health & Awareness'],          88),
    (['aviation', 'car-culture', 'music', 'square-dancer',
      'j-p-patches'],                                  CAT['Arts / Culture'],              82),
    (['chehalis-tribe', 'muckleshoot', 'puyallup-tribe'],
                                                       CAT['Other / Specialty'],           78),
]
WA_CIVIC_DEFAULT = (CAT['Other / Specialty'], 72)

# wa-standard-issue: filenames starting with 'standard-issue' → std-issue series
# everything else stays in specialty series with keyword category
WA_STD_ISSUE_RULES = [
    (['amateur-radio', 'mars'],                        CAT['Radio / Amateur Radio'],      95),
    (['disabled-american-veteran', 'veteran-military'],CAT['Military / Veteran'],         90),
    (['disabled-parking'],                             CAT['Disabled / Accessibility'],   90),
    (['honorary-consular'],                            CAT['Government / Exempt'],        88),
    (['collector-vehicle', 'horseless-carriage',
      'throwback'],                                    CAT['Historical / Commemorative'], 88),
    (['ev-electric', 'rideshare'],                     CAT['Other / Specialty'],          80),
]

# ── AB lookup tables (require CAT to be defined above) ───────────────────────────
# Plates NOT matching 'standard-issue' in core and NOT the bare 'motorcycle' plate
# are routed to AB_SPECIALTY_SERIES and categorized by these rules.
# (order matters — first match wins)
AB_SPECIALTY_RULES = [
    (['antique-auto'],                CAT['Historical / Commemorative'], 90),
    (['calgary-flames',
      'edmonton-oilers'],             CAT['Sports Team'],                90),
    (['disabled'],                    CAT['Disabled / Accessibility'],   90),
    (['support-our-troops',
      'veteran'],                     CAT['Military / Veteran'],         90),
    (['trailer'],                     CAT['Other / Specialty'],          78),
]

# ── AK lookup tables (require CAT to be defined above) ───────────────────────────
# Subfolders: ak-standard-issue, ak-veteran, ak-schools, ak-specialty, ak-non-passenger
# Category = subfolder assignment; vehicle class unknown defaults to Other.
AK_SUBFOLDER_CATEGORIES = {
    'ak-schools': {'cat_id': CAT['School'],             'conf': 95},
    'ak-veteran': {'cat_id': CAT['Military / Veteran'], 'conf': 95},
    # ak-specialty, ak-standard-issue, ak-non-passenger use keyword rules below
}

# ak-standard-issue: keyword-based category override within the std-issue series
AK_STD_ISSUE_RULES = [
    (['standard-issue', 'mountain'],      CAT['Standard Issue'],             95),
    (['amateur-radio'],                   CAT['Radio / Amateur Radio'],       95),
    (['custom-collector', 'historic'],    CAT['Historical / Commemorative'], 88),
    (['disabled'],                        CAT['Disabled / Accessibility'],    90),
]
AK_STD_ISSUE_DEFAULT = (CAT['Standard Issue'], 85)

# ak-specialty: keyword rules — first match wins
AK_SPECIALTY_RULES = [
    (['firefighter', 'fire-fighters', 'iaff',
      'fallen-officer'],                  CAT['First Responder'],             90),
    (['freemason', 'knights-of-columbus',
      'lions-club', 'pioneers-of-alaska'],CAT['Fraternal / Civic'],           88),
    (['cancer', 'blood-bank', 'childrens-trust',
      'choose-life', 'breast'],          CAT['Health & Awareness'],           88),
    (['celebrating-the-arts'],            CAT['Arts / Culture'],              88),
    (['iditarod'],                        CAT['Sports Team'],                  88),
    (['support-our-troops',
      'veterans-commemorative'],          CAT['Military / Veteran'],           90),
]
AK_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# ak-non-passenger: keyword rules — all routed to Specialty series, vehicle class Other
AK_NON_PASSENGER_RULES = [
    (['statetrooper', 'exempt'],          CAT['Government / Exempt'],         90),
    (['farm-vehicle'],                    CAT['Agricultural'],                 88),
    (['comm-trailer'],                    CAT['Other / Specialty'],            78),
]
AK_NON_PASSENGER_DEFAULT = (CAT['Government / Exempt'], 80)

# ── AL lookup tables (require CAT to be defined above) ───────────────────────────
# Direct subfolder → category mapping (al-specialty/standard-issue/non-passenger use rules)
AL_SUBFOLDER_CATEGORIES = {
    'al-fraternal': {'cat_id': CAT['Fraternal / Civic'],          'conf': 95},
    'al-outdoor':   {'cat_id': CAT['Conservation / Environment'], 'conf': 92},
    'al-schools':   {'cat_id': CAT['School'],                     'conf': 95},
    'al-veteran':   {'cat_id': CAT['Military / Veteran'],         'conf': 95},
}

# al-non-passenger keyword rules — all go to Specialty series, vehicle class Other (or Motorcycle if in filename)
AL_NON_PASSENGER_RULES = [
    (['consular'],                 CAT['Government / Exempt'],     90),
    (['dealer'],                   CAT['Dealer / Manufacturer'],   90),
    (['manufacturer'],             CAT['Dealer / Manufacturer'],   90),
    (['rescue-squad'],             CAT['First Responder'],         88),
    (['cotton', 'farm'],           CAT['Agricultural'],            88),
]
AL_NON_PASSENGER_DEFAULT = (CAT['Other / Specialty'], 78)

# al-specialty keyword rules — first match wins
AL_SPECIALTY_RULES = [
    (['amateur-radio'],                              CAT['Radio / Amateur Radio'],          95),
    (['firefighter', 'fire-', 'fighter',
      'emergency-medical', 'law-enforcement',
      'fraternal-order-of-police'],                  CAT['First Responder'],                88),
    (['freemason'],                                  CAT['Fraternal / Civic'],              90),
    (['cancer', 'autism', 'breast', 'epilepsy',
      'sickle-cell', 'diabetes', 'cystic-fibrosis',
      'mending-kids', 'choose-life',
      'domestic-violence', 'spay-neuter', 'shriners',
      'habitat-for-humanity', 'curing-childhood',
      'hope-for-kids', 'keeping-families',
      'ronald-mcdonald', 'nurses',
      'drive-out-ovarian', 'colon-cancer',
      'in-memory', 'stop-domestic'],                CAT['Health & Awareness'],             88),
    (['support-the-arts'],                           CAT['Arts / Culture'],                 88),
    (['barber-vintage', 'bicentennial',
      'sons-of-confederate'],                        CAT['Historical / Commemorative'],     88),
    (['helping-schools', 'educator',
      'lurleen-w-wallace', 'university', 'college'], CAT['School'],                         82),
    (['dare-to-explore'],                            CAT['Conservation / Environment'],     82),
    (['gold-star', 'state-defense'],                 CAT['Military / Veteran'],             88),
]
AL_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# ── AR lookup tables (require CAT to be defined above) ───────────────────────────
# Direct subfolder → category (ar-specialty/standard-issue/non-passenger use rules)
AR_SUBFOLDER_CATEGORIES = {
    'ar-fraternal': {'cat_id': CAT['Fraternal / Civic'],          'conf': 95},
    'ar-outdoors':  {'cat_id': CAT['Conservation / Environment'], 'conf': 92},
    'ar-schools':   {'cat_id': CAT['School'],                     'conf': 95},
    'ar-sports':    {'cat_id': CAT['Sports Team'],                'conf': 90},
    'ar-veteran':   {'cat_id': CAT['Military / Veteran'],         'conf': 95},
}

# ar-non-passenger keyword rules — vehicle class Other, series 668
AR_NON_PASSENGER_RULES = [
    (['ambulance'],                CAT['First Responder'],        88),
    (['school-vehicle'],           CAT['Government / Exempt'],    88),
    (['justice-of-the-peace'],     CAT['Government / Exempt'],    90),
    (['taxi'],                     CAT['Other / Specialty'],      78),
    (['bus'],                      CAT['Other / Specialty'],      78),
    (['transporter', 'hearse'],    CAT['Other / Specialty'],      78),
]
AR_NON_PASSENGER_DEFAULT = (CAT['Other / Specialty'], 78)

# ar-standard-issue category overrides (non-standard plates kept in std-issue series)
AR_STD_ISSUE_CAT_RULES = [
    (['antique', 'street-rod', 'custom-vehicle'], CAT['Historical / Commemorative'], 88),
    (['persons-with-disabilities'],               CAT['Disabled / Accessibility'],   90),
]
AR_STD_ISSUE_CAT_DEFAULT = (CAT['Standard Issue'], 95)

# ar-specialty keyword rules — first match wins
AR_SPECIALTY_RULES = [
    (['amateur-radio'],                                 CAT['Radio / Amateur Radio'],         95),
    (['fire-fighter', 'firefighter', 'emergency-medical',
      'municipal-police', 'sheriffs', 'sheriff',
      'fraternal-order-of-police', 'search-and-rescue',
      'civil-air-patrol'],                             CAT['First Responder'],                88),
    (['freemason', 'grand-lodge', 'kappa-alpha-psi',
      'prince-hall', 'boy-scouts'],                    CAT['Fraternal / Civic'],              88),
    (['rice-council', 'cattlemen',
      'agricultural-education', 'ffa'],                CAT['Agricultural'],                   88),
    (['support-our-troops', 'little-rock-air-force'],  CAT['Military / Veteran'],             88),
    (['sons-of-confederate'],                          CAT['Historical / Commemorative'],     88),
    (['committed-to-education', 'school-for-the-deaf'],CAT['School'],                         82),
    (['martin-luther-king'],                           CAT['Arts / Culture'],                 82),
    (['cancer', 'autism', 'childhood', 'choose-life',
      'domestic-violence', 'down-syndrome', 'hospice',
      'multiple-sclerosis', 'organ-donor', 'spay',
      'humane-society', 'animal-rescue', 'court-appointed',
      'susan-g-komen'],                               CAT['Health & Awareness'],              88),
]
AR_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# ── AZ lookup tables (require CAT to be defined above) ───────────────────────────
# Direct subfolder → category (az-specialty/standard-issue/non-passenger use rules)
AZ_SUBFOLDER_CATEGORIES = {
    'az-veteran': {'cat_id': CAT['Military / Veteran'],         'conf': 95},
    'az-schools': {'cat_id': CAT['School'],                     'conf': 95},
    'az-sports':  {'cat_id': CAT['Sports Team'],                'conf': 90},
    'az-outdoors':{'cat_id': CAT['Conservation / Environment'], 'conf': 90},
}

# Keywords that force routing to 1980 series + Standard Issue, regardless of year in filename
AZ_CLASSIC_KEYWORDS = ['street-rod', 'classic-car', 'horseless-carriage', 'historic-vehicle']

# az-non-passenger keyword rulesAZ
AZ_NON_PASSENGER_RULES = [
    (['farm-vehicle'],         CAT['Agricultural'],           88),
    (['dealer'],               CAT['Dealer / Manufacturer'],  90),
    (['commercial'],           CAT['Other / Specialty'],      78),
]
AZ_NON_PASSENGER_DEFAULT = (CAT['Other / Specialty'], 78)

# az-standard-issue: category overrides for variant plates that stay in std-issue series
AZ_STD_ISSUE_CAT_RULES = [
    (['amateur-radio'],                             CAT['Radio / Amateur Radio'],       95),
    (['deaf-hard-of-hearing', 'disabled-person'],   CAT['Disabled / Accessibility'],    90),
]
AZ_STD_ISSUE_CAT_DEFAULT = (CAT['Standard Issue'], 95)

# az-specialty keyword rules — first match wins
AZ_SPECIALTY_RULES = [
    (['fire-fighter', 'firefighter', 'fallenhero',
      'fallen-hero', 'honoring-fallen',
      'first-responder', 'fraternal-order-of-police',
      'support-public-safety', 'support-firefighter',
      'professional-fire-fighters'],                CAT['First Responder'],              88),
    (['freemason', 'boy-scouts', 'girl-scouts',
      'rotary-international'],                      CAT['Fraternal / Civic'],            88),
    (['4h', 'ffa-agriculture'],                     CAT['Agricultural'],                 88),
    (['luke-air-force', 'national-guard'],           CAT['Military / Veteran'],           88),
    (['arizona-centennial', 'arizona-historical',
      'route-66', 'state-forty-eight',
      'barrett-jackson'],                           CAT['Historical / Commemorative'],   88),
    (['cancer', 'autism', 'alzheimer',
      'congenital-heart', 'organ-donor', 'donate-life',
      'child-abuse', 'habitat-for-humanity',
      'make-a-wish', 'no-child-grieves',
      'spay-neuter', 'pet-friendly-spay',
      'ending-hunger', 'keep-hearts', 'end-alzheimer',
      'childhood-cancer', 'choose-life', 'ovarian-cancer'],
                                                    CAT['Health & Awareness'],           88),
    (['pbs', 'arizona-highways',
      'alice-coopers', 'arizona-science-center'],   CAT['Arts / Culture'],               82),
    (['character-education', 'support-our-schools',
      'arizona-education'],                         CAT['School'],                       82),
]
AZ_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# ── CT lookup tables ───────────────────────────────────────────────────────────────
CT_SUBFOLDER_CATEGORIES = {
    'ct-fraternal':    {'cat_id': None, 'conf': 88, 'key': 'Fraternal / Civic'},
    'ct-non-passenger':{'cat_id': None, 'conf': 78, 'key': 'Other / Specialty'},
    'ct-outdoor':      {'cat_id': None, 'conf': 90, 'key': 'Conservation / Environment'},
    'ct-schools':      {'cat_id': None, 'conf': 95, 'key': 'School'},
    'ct-sports':       {'cat_id': None, 'conf': 90, 'key': 'Sports Team'},
    'ct-veteran':      {'cat_id': None, 'conf': 95, 'key': 'Military / Veteran'},
}
# Filled after CAT is defined (see init block at bottom of lookup section)

CT_SPECIALTY_RULES = [
    (['firefighters', 'police-commissioners', 'police-memorial',
      'blue-knights', 'operation-lifesaver',
      'uniformed-professional-firefighters'],        CAT['First Responder'],             88),
    (['cure-kids', 'cure-prostate', 'celebrate-nursing', 'keep-kids-safe',
      'children-first', 'fidelco', 'animal-population',
      'lions-eye'],                                  CAT['Health & Awareness'],           88),
    (['amistad', 'new-england-air-museum',
      'p-t-barnum', 'preservation-connecticut'],     CAT['Historical / Commemorative'],   88),
    (['candlewood-lake'],                            CAT['Conservation / Environment'],   88),
    (['city-of', 'town-of', 'iuoe'],                CAT['Fraternal / Civic'],            82),
    (['ferrari'],                                   CAT['Other / Specialty'],            72),
]
CT_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# Resolve deferred subfolder category IDs now that CAT is defined
for _sf, _v in CT_SUBFOLDER_CATEGORIES.items():
    _v['cat_id'] = CAT[_v['key']]

# ── DC lookup tables ───────────────────────────────────────────────────────────
DC_SPECIALTY_RULES = [
    (['fire-fighters', 'blue-knights'],          CAT['First Responder'],             88),
    (['breast-cancer', 'children-first',
      'donate-life'],                            CAT['Health & Awareness'],           88),
    (['porsche', 'bad-boys'],                    CAT['Other / Specialty'],            72),
    (['spirit-of-faith'],                        CAT['Other / Specialty'],            72),
]
DC_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# ── IN lookup tables ──────────────────────────────────────────────────────────
# in-standard-issue: filename-keyed overrides for non-standard plates kept in std
# Name overrides for known acronym / formatting issues in Indiana filenames
IN_NAME_OVERRIDES = {
    'in-d-a-r-e-indiana-trust':                     'D.A.R.E. Indiana Trust',
    'in-rv':                                         'RV',
    'in-iupui':                                      'IUPUI',
    'in-wfyi-public-media':                          'WFYI Public Media',
    'in-iuoe-local-150-scholarship-fund-inc':        'IUOE Local 150 Scholarship Fund Inc',
    'in-ex-pow':                                     'Ex-POW',
    'in-pow-mia':                                    'POW-MIA',
    'in-fleet-vehicle2':                             'Fleet Vehicle (Alternate)',
}
# series routing (year-based) is handled directly in parse_in()

# in-sports: in-environmental is Conservation; everything else is Sports Team
IN_SPORTS_RULES = [
    (['environmental'],        CAT['Conservation / Environment'], 88),
    (['special-olympics'],     CAT['Health & Awareness'],         80),
    (['bicycle-coalition'],    CAT['Other / Specialty'],          78),
]
IN_SPORTS_DEFAULT = (CAT['Sports Team'], 90)

# in-specialty keyword rules — first match wins
IN_SPECIALTY_RULES = [
    (['amateur-radio'],                                 CAT['Radio / Amateur Radio'],         95),
    (['state-police', 'firefighter', 'fire-fighter',
      'ems', 'sheriff', 'chiefs-of-police',
      'emergency-medical', 'emergency-services',
      'volunteer-firefighter', 'professional-firefighter',
      'first-responders'],                              CAT['First Responder'],               88),
    (['freemason', 'lodge', 'knights-of-columbus',
      'shrine', 'lions', 'fraternal-order-of-police',
      'ymca', 'boys-and-girls-club', 'boy-scouts',
      'd-a-r-e', 'iuoe',
      'sisterhood-united', 'habitat-for-humanity',
      'american-legion'],                               CAT['Fraternal / Civic'],             88),
    (['4h', 'ffa', 'future-farmers', 'farm-bureau'],    CAT['Agricultural'],                  88),
    (['lincoln', 'lewis-and-clark', 'coal-mining',
      'bicentennial', 'native-american'],               CAT['Historical / Commemorative'],    88),
    (['cancer', 'autism', 'diabetes', 'juvenile',
      'blood-center', 'riley-hospital', 'down-syndrome',
      'lupus', 'breast-cancer', 'suicide-prevention',
      'als', 'donate-life', 'organ', 'foster',
      'a-kid-again', 'peyton-manning', 'health',
      'pregnancy-centers', 'nurse', 'kids-first'],      CAT['Health & Awareness'],            88),
    (['support-our-troops', 'marine-foundation',
      'patriot-guard', 'military'],                     CAT['Military / Veteran'],            88),
    (['zoo', 'zoological', 'recycling', 'circular',
      'greenways', 'pet-friendly', 'wild-turkey',
      'ducks-unlimited'],                               CAT['Conservation / Environment'],    88),
    (['arts-trust', 'music-education', 'wfyi',
      'black-expo', 'public-media'],                    CAT['Arts / Culture'],                82),
    (['department-of-education', 'rose-hulman',
      'delta-research'],                                CAT['School'],                        82),
]
IN_SPECIALTY_DEFAULT = (CAT['Other / Specialty'], 72)

# ── Helpers ───────────────────────────────────────────────────────────────────
SMALL_WORDS = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor',
               'on', 'at', 'to', 'by', 'in', 'of', 'v', 'vs'}

def to_title(slug_core: str) -> str:
    """Convert slug-style 'bronze-star-of-valor' to 'Bronze Star of Valor'."""
    words = slug_core.replace('-', ' ').split()
    result = []
    for i, w in enumerate(words):
        result.append(w if (i > 0 and w in SMALL_WORDS) else w.capitalize())
    return ' '.join(result)


def slug_from_name(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", '-', s)
    return s.strip('-')


def run_mysql(sql: str) -> str:
    """Run a SQL query and return stdout."""
    env = os.environ.copy()
    result = subprocess.run(
        [MYSQL_BIN, f'-u{DB_USER}', f'-p{DB_PASS}',
         '-h', DB_HOST, '-P', DB_PORT, DB_NAME, '-e', sql],
        capture_output=True, text=True, env=env
    )
    return result.stdout


def fetch_existing_slugs() -> set:
    out = run_mysql("SELECT slug FROM plates;")
    return {line.strip() for line in out.splitlines() if line.strip() and line.strip() != 'slug'}


def unique_slug(base_slug: str, existing: set) -> str:
    if base_slug not in existing:
        return base_slug
    n = 2
    while f"{base_slug}-{n}" in existing:
        n += 1
    return f"{base_slug}-{n}"


# ── TN parser ─────────────────────────────────────────────────────────────────
def parse_tn(stem: str) -> dict:
    notes = []

    if stem.startswith('in-'):
        notes.append('WARNING: filename starts with "in-" not "tn-" — verify this belongs to TN')
        core = stem[3:]
    elif stem.startswith('tn-'):
        core = stem[3:]
    else:
        return None

    # Strip version suffix (-v2, -v3)
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version = f' V{vm.group(1)}'
        core = core[:vm.start()]

    # Series
    series = TN_SERIES_MAP.get(stem, TN_DEFAULT_SERIES)

    # Category via suffix rules
    cat_id, cat_conf, name_core = None, 0, core
    for suffix, cid, conf in TN_SUFFIX_RULES:
        if core.endswith(suffix):
            cat_id, cat_conf = cid, conf
            name_core = core[:-len(suffix)]
            break

    # Strip standard-issue from name core
    if 'standard-issue' in name_core:
        cat_id, cat_conf = CAT['Standard Issue'], 90
        name_core = re.sub(r'standard-issue-?', '', name_core).strip('-')

    # Category via keyword fallback
    if cat_id is None or cat_conf < 70:
        for keywords, cid, conf in TN_KEYWORD_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text = to_title(name_core.strip('-'))
    plate_name = f"TN-{name_text}{version}"

    # All TN plates in this batch are Passenger (no motorcycle/pwd in filenames)
    vehicle_class = 'Passenger'

    return {
        'filename': stem + '.jpg',
        'plate_name': plate_name,
        'slug': slug_from_name(plate_name),
        'category_id':   cat_id   if cat_conf   >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id']   if series['conf'] >= 70 else None,
        'series_conf':   series['conf'],
        'notes': notes,
    }


# ── CO parser ─────────────────────────────────────────────────────────────────
def parse_co(stem: str) -> dict:
    if not stem.startswith('co-'):
        return None

    core = stem[3:]

    # Vehicle class + PWD detection
    vehicle_class = 'Passenger'
    is_pwd = False

    if core.endswith('-motorcycle-pwd'):
        vehicle_class = 'Motorcycle'
        is_pwd = True
        core = core[:-len('-motorcycle-pwd')]
    elif core.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        core = core[:-len('-motorcycle')]
    elif core.endswith('-passenger-pwd'):
        is_pwd = True
        core = core[:-len('-passenger-pwd')]
    elif core.endswith('-pwd'):
        is_pwd = True
        core = core[:-len('-pwd')]

    # Category via keyword rules
    cat_id, cat_conf = None, 0
    for keywords, cid, conf in CO_KEYWORD_RULES:
        if any(kw in core for kw in keywords):
            cat_id, cat_conf = cid, conf
            break

    # PWD override: if no strong category, use Disabled/Accessibility
    if is_pwd and (cat_id is None or cat_conf < 70):
        cat_id, cat_conf = CAT['Disabled / Accessibility'], 85

    # Build plate name
    name_text = to_title(core)
    suffix = ''
    if vehicle_class == 'Motorcycle' and is_pwd:
        suffix = ' Motorcycle PWD'
    elif vehicle_class == 'Motorcycle':
        suffix = ' Motorcycle'
    elif is_pwd:
        suffix = ' Passenger PWD'

    plate_name = f"CO-{name_text}{suffix}"

    return {
        'filename': stem + '.jpg',
        'plate_name': plate_name,
        'slug': slug_from_name(plate_name),
        'category_id':   cat_id   if cat_conf   >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     CO_DEFAULT_SERIES['id'],
        'series_conf':   CO_DEFAULT_SERIES['conf'],
        'notes': [],
    }


# ── FL parser ─────────────────────────────────────────────────────────────────
def parse_fl(stem: str, subfolder: str, actual_filename: str):
    """Parse a single FL plate image file.

    Args:
        stem:            Path.stem of the file (may contain embedded .png for .png.jpg files)
        subfolder:       Name of the subfolder (e.g. 'fl-military')
        actual_filename: The real filename including extension, used for DB and image copy
    """
    # Skip Windows duplicate files
    if ' - Copy' in stem or ' - copy' in stem:
        return None

    # Normalize stem: strip embedded .png suffix (e.g. from 'fl-foo.png.jpg')
    clean_stem = stem
    if clean_stem.lower().endswith('.png'):
        clean_stem = clean_stem[:-4]

    if not clean_stem.lower().startswith('fl-'):
        return None

    core = clean_stem[3:]  # strip 'fl-'

    # v2 / v3 detection
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version = f' V{vm.group(1)}'
        core = core[:vm.start()]

    # Vehicle class: motorcycle plates have 'motorcycle' in the filename core
    vehicle_class = 'Motorcycle' if 'motorcycle' in core else 'Passenger'

    # Category assignment
    subcat = FL_SUBFOLDER_CATEGORIES.get(subfolder)
    if subcat is not None:
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']
    else:
        # fl-special-interest: keyword rules
        cat_id, cat_conf = CAT['Other / Specialty'], 72
        for keywords, cid, conf in FL_SPECIAL_INTEREST_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    # Build plate name: 'FL - {Title Case}{version}'
    name_text = to_title(core)
    plate_name = f'FL - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     FL_DEFAULT_SERIES['id'],
        'series_conf':   FL_DEFAULT_SERIES['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── WA parser ─────────────────────────────────────────────────────────────────
def parse_wa(stem: str, subfolder: str, actual_filename: str):
    """Parse a single WA plate image file across 6 subfolders."""
    if not stem.lower().startswith('wa-'):
        return None  # skips .lnk shortcuts and any non-wa files

    core_raw = stem[3:]
    core = core_raw.lower()

    # v2/v3 detection
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core = core[:vm.start()]

    vehicle_class = 'Passenger'  # WA has no motorcycle variants in this set

    subcat = WA_SUBFOLDER_CATEGORIES.get(subfolder)

    if subcat is not None:
        # Direct subfolder assignment
        cat_id   = subcat['cat_id']
        cat_conf = subcat['conf']
        series   = WA_SPECIALTY_SERIES

    elif subfolder == 'wa-sports':
        cat_id, cat_conf = WA_SPORTS_DEFAULT
        for keywords, cid, conf in WA_SPORTS_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break
        series = WA_SPECIALTY_SERIES

    elif subfolder == 'wa-civic':
        cat_id, cat_conf = WA_CIVIC_DEFAULT
        for keywords, cid, conf in WA_CIVIC_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break
        series = WA_SPECIALTY_SERIES

    else:  # wa-standard-issue
        if core.startswith('standard-issue'):
            cat_id, cat_conf = CAT['Standard Issue'], 95
            series = WA_STD_ISSUE_SERIES
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72
            series = WA_SPECIALTY_SERIES
            for keywords, cid, conf in WA_STD_ISSUE_RULES:
                if any(kw in core for kw in keywords):
                    cat_id, cat_conf = cid, conf
                    break

    name_text = to_title(core_raw)
    plate_name = f'WA - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── KY parser ─────────────────────────────────────────────────────────────────
def parse_ky(stem: str, subfolder: str, actual_filename: str):
    """Parse a single KY plate image file across 6 subfolders."""
    if not stem.lower().startswith('ky-'):
        return None  # skips blank-license-plate-renamer.png and any other non-wa files

    core_raw = stem[3:]           # strip 'ky-', preserve original case
    core = core_raw.lower()       # lowercase for all matching

    # v2/v3 detection
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core = core[:vm.start()]

    # Motorcycle / disabled suffix stripping (order matters — longest first)
    vehicle_class = 'Passenger'
    display_core = core_raw
    if core.endswith('-motorcycle-disabled'):
        vehicle_class = 'Motorcycle'
        display_core = core_raw[:-len('-motorcycle-disabled')]
        core = core[:-len('-motorcycle-disabled')]
    elif core.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        display_core = core_raw[:-len('-motorcycle')]
        core = core[:-len('-motorcycle')]
    elif core.endswith('-disabled'):
        display_core = core_raw[:-len('-disabled')]
        core = core[:-len('-disabled')]

    # Category assignment
    subcat = KY_SUBFOLDER_CATEGORIES.get(subfolder)
    if subcat is not None:
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']
    elif subfolder == 'ky-commercial':
        cat_id, cat_conf = KY_COMMERCIAL_DEFAULT
        for keywords, cid, conf in KY_COMMERCIAL_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break
    elif subfolder == 'ky-miscellaneous':
        cat_id, cat_conf = KY_MISC_DEFAULT
        for keywords, cid, conf in KY_MISC_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break
    else:  # ky-special-interest
        cat_id, cat_conf = CAT['Other / Specialty'], 72
        for keywords, cid, conf in KY_SPECIAL_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text = to_title(display_core)
    plate_name = f'KY - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     KY_DEFAULT_SERIES['id'],
        'series_conf':   KY_DEFAULT_SERIES['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── OR parser ─────────────────────────────────────────────────────────────────
def parse_or(stem: str) -> dict:
    """Parse a single OR plate image file. All plates are Military / Veteran."""
    if not stem.lower().startswith('or-'):
        return None

    core = stem[3:]  # strip 'or-'

    # v2 / v3 detection
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version = f' V{vm.group(1)}'
        core = core[:vm.start()]

    vehicle_class = 'Motorcycle' if 'motorcycle' in core else 'Passenger'

    name_text = to_title(core)
    plate_name = f'OR - {name_text}{version}'

    return {
        'filename':      stem + '.png',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   CAT['Military / Veteran'],
        'category_conf': 95,
        'vehicle_class': vehicle_class,
        'series_id':     OR_DEFAULT_SERIES['id'],
        'series_conf':   OR_DEFAULT_SERIES['conf'],
        'notes':         [],
        'src_subfolder': '',
    }


# ── DE parser ─────────────────────────────────────────────────────────────────
def parse_de(stem: str, subfolder: str, actual_filename: str):
    """Parse a single DE (Delaware) plate image across 7 subfolders.

    Series routing: all plates → DE_SERIES (682)
      Proofread pass will reassign specialty → 683 and B&W reissue → 684.

    Category routing:
      de-fraternal     → Fraternal / Civic (88%)
      de-outdoors      → Conservation / Environment (90%)
      de-schools       → School (95%)
      de-sports        → Sports Team (90%)
      de-veteran       → Military / Veteran (95%)
                         '-parking' or 'dav-special-parking' → Disabled/Accessibility
                         '-handicapped' or 'purple-heart-handicapped' → Disabled/Accessibility
      de-standard-issue→ keyword overrides (radio, antique, handicapped, street-rod)
      de-specialty     → keyword rules

    Vehicle class:
      '-motorcycle' in filename → Motorcycle
      default → Passenger
    """
    if not stem.lower().startswith('de-'):
        return None

    core_raw = stem[3:]           # strip 'de-', preserve case
    core     = core_raw.lower()   # lowercase for matching

    # Strip version suffix (-v1, -v2, etc.)
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version  = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core     = core[:vm.start()]

    vehicle_class = 'Motorcycle' if 'motorcycle' in core else 'Passenger'

    if subfolder == 'de-fraternal':
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'de-outdoors':
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'de-schools':
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'de-sports':
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'de-veteran':
        if 'parking' in core or 'handicapped' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'de-standard-issue':
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'antique' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'handicapped' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif 'street-rod' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    else:  # de-specialty (and any unexpected subfolder)
        if 'law-enforcement-memorial' in core:
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        elif any(kw in core for kw in ['firefighter', 'fire-department', 'civil-air-patrol',
                                        'law-enforcement', 'police', 'paramedic', 'correctional']):
            cat_id, cat_conf = CAT['First Responder'], 88
        elif any(kw in core for kw in ['breast-cancer', 'cancer-support', 'autism',
                                        'conquer-childhood', 'organ-donor', 'donate-life',
                                        'attack-addiction', 'stop-child-abuse',
                                        'suicide-prevention', 'choose-life']):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ['caesar-rodney', 'semiquincentennial',
                                        'porceain-reproduction', 'stainless-steel-reproduction']):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core for kw in ['nanticoke']):
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        elif any(kw in core for kw in ['dsea-education']):
            cat_id, cat_conf = CAT['School'], 82
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    name_text  = to_title(core_raw)
    plate_name = f'DE - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     DE_SERIES['id'],
        'series_conf':   DE_SERIES['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── IA parser ─────────────────────────────────────────────────────────────────
def parse_ia(stem: str, subfolder: str, actual_filename: str):
    """Parse a single IA (Iowa) plate image across 9 subfolders.

    Series routing:
      ia-standard-issue → IA_SERIES_STANDARD (689)
      all other subfolders → IA_SERIES_SPECIALTY (690)

    Category routing:
      ia-first-responder → First Responder (95%);
                           ia-fallen-peace-officer → Other/Specialty (72%)
      ia-fraternal       → Fraternal / Civic (88%)
      ia-outdoors        → Conservation / Environment (90%)
      ia-schools         → School (95%)
      ia-sports          → Sports Team (90%)
      ia-veteran         → Military / Veteran (95%);
                           'disabled' in core → Disabled / Accessibility (90%)
      ia-standard-issue  → keyword overrides (radio, disabled, blackout, standard-issue)
      ia-specialty       → keyword rules

    Vehicle class:
      'motorcycle' suffix in filename → Motorcycle
      default → Passenger
    """
    if not stem.lower().startswith('ia-'):
        return None

    core_raw = stem[3:]           # strip 'ia-', preserve case
    core     = core_raw.lower()   # lowercase for matching

    # Strip version suffix (-v1, -v2, etc.)
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version  = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core     = core[:vm.start()]

    # Motorcycle suffix handling
    if core.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        core_raw = core_raw[:-len('-motorcycle')]
        core     = core[:-len('-motorcycle')]
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    # ── Series: standard-issue → 689, all else → 690 ──────────────────────
    series = IA_SERIES_STANDARD if subfolder == 'ia-standard-issue' else IA_SERIES_SPECIALTY

    # ── Category routing ───────────────────────────────────────────────
    if subfolder == 'ia-first-responder':
        if core == 'fallen-peace-officer':
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:
            cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'ia-fraternal':
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'ia-outdoors':
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'ia-schools':
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'ia-sports':
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'ia-veteran':
        if 'disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'ia-standard-issue':
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disabled' in core or 'disabilities' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif core == 'black-out-design':
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    else:  # ia-specialty (and any unexpected subfolder)
        if any(kw in core for kw in ['beat-cancer', 'breast-cancer', 'choose-life',
                                      'lifeserve', 'organ-and-tissue', 'little-superheroes',
                                      'love-our-kids', 'steps-of-hope', 'trice-legacy',
                                      'no-foot-too-small']):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ['cattlemen', 'pork-producers']):
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif 'iowa-heritage' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'governor-medal-of-valor' in core:
            cat_id, cat_conf = CAT['Military / Veteran'], 95
        elif 'boy-scouts' in core:
            cat_id, cat_conf = CAT['Fraternal / Civic'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    name_text  = to_title(core_raw)
    plate_name = f'IA - {name_text}{moto_suffix}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── ID parser ─────────────────────────────────────────────────────────────────
def parse_id(stem: str, subfolder: str, actual_filename: str):
    """Parse a single ID (Idaho) plate image across 9 subfolders.

    Series routing:
      ALL plates → ID_SERIES_SCENIC (691)
      Series 692 (Specialty) will be populated manually in Filament later.

    Category routing:
      id-first-responder → First Responder (95%)
      id-fraternal       → Fraternal / Civic (88%)
      id-non-passenger   → Other / Specialty (72%), vehicle class Other
      id-outdoors        → Conservation / Environment (90%);
                           agriculture/rangeland → Agricultural (88%);
                           snowmobile/snowskier/white-water-rafting → Sports Team (90%)
      id-schools         → School (95%)
      id-specialty       → keyword rules
      id-sports          → Sports Team (90%)
      id-standard-issue  → keyword overrides (disabled, radio, antique/classic, world-famous-potatoes, etc.)
      id-veteran         → Military / Veteran (95%);
                           disabled-veteran* → Disabled / Accessibility (90%)

    Vehicle class:
      id-non-passenger subfolder → Other
      -motorcycle stem           → Motorcycle
      default                    → Passenger
    """
    if not stem.lower().startswith('id-'):
        return None

    core_raw = stem[3:]          # strip 'id-', preserve case
    core     = core_raw.lower()  # lowercase for matching

    # ── Motorcycle detection ───────────────────────────────────────────────────
    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    series = ID_SERIES_SCENIC   # ALL plates → 691

    # ── Non-passenger ──────────────────────────────────────────────────────────
    if subfolder == 'id-non-passenger':
        vehicle_class    = 'Other'
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── First responder ────────────────────────────────────────────────────────
    elif subfolder == 'id-first-responder':
        cat_id, cat_conf = CAT['First Responder'], 95

    # ── Fraternal ──────────────────────────────────────────────────────────────
    elif subfolder == 'id-fraternal':
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    # ── Outdoors ───────────────────────────────────────────────────────────────
    elif subfolder == 'id-outdoors':
        if any(kw in core for kw in ('agriculture', 'rangeland')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif any(kw in core for kw in ('snowmobile', 'snowskier', 'white-water-rafting')):
            cat_id, cat_conf = CAT['Sports Team'], 90
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90

    # ── Schools ────────────────────────────────────────────────────────────────
    elif subfolder == 'id-schools':
        cat_id, cat_conf = CAT['School'], 95

    # ── Sports ─────────────────────────────────────────────────────────────────
    elif subfolder == 'id-sports':
        cat_id, cat_conf = CAT['Sports Team'], 90

    # ── Veteran ────────────────────────────────────────────────────────────────
    elif subfolder == 'id-veteran':
        if 'disabled-veteran' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif 'purple-heart-disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    # ── Standard-issue ─────────────────────────────────────────────────────────
    elif subfolder == 'id-standard-issue':
        if 'radio-amateur' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif any(kw in core for kw in ('classic', 'old-timer', 'sesqucentennial', 'year-of-manufacture')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core for kw in ('street-rod', 'custom-vehicle', 'americas-sports-car', 'blackout')):
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    # ── Specialty ──────────────────────────────────────────────────────────────
    else:  # id-specialty and any unexpected subfolder
        if 'choose-life' in core:
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('centennial', 'capital-restoration', 'lewis-clark')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif '4h' in core:
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif 'rotary-international' in core:
            cat_id, cat_conf = CAT['Fraternal / Civic'], 88
        elif 'firefighters' in core:
            cat_id, cat_conf = CAT['First Responder'], 95
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── Name overrides (typo corrections) ─────────────────────────────────────
    ID_NAME_OVERRIDES = {
        'id-former-prisioner-of-war-korea':        'Former Prisoner of War Korea',
        'id-former-prisioner-of-war-persian-gulf': 'Former Prisoner of War Persian Gulf',
        'id-former-prisioner-of-war-uss-pueblo':   'Former Prisoner of War USS Pueblo',
        'id-former-prisioner-of-war-vietnam':      'Former Prisoner of War Vietnam',
        'id-former-prisioner-of-war-world-war-ii': 'Former Prisoner of War World War II',
        'id-sesqucentennial':                      'Sesquicentennial',
        'id-motorcycle-custom':                    'Custom Motorcycle',
        'id-motorcycle-disabled':                  'Disabled Motorcycle',
        'id-4h':                                   '4-H',
    }
    override_key = f'id-{core_raw.lower()}'
    if override_key in ID_NAME_OVERRIDES:
        name_text = ID_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'ID - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── IN parser ─────────────────────────────────────────────────────────────────
def parse_in(stem: str, subfolder: str, actual_filename: str):
    """Parse a single IN (Indiana) plate image across 9 subfolders.

    Series routing:
      in-standard-issue:
        year 2017 (or non-year extras) → IN_STD_2017_SERIES (696)
        year 2013                      → IN_STD_2013_SERIES (697)
        year 2008                      → IN_STD_2008_SERIES (698)
        year 2003                      → IN_STD_2003_SERIES (699)
        year 1998                      → IN_STD_1998_SERIES (700)
      in-non-passenger                 → IN_NON_PASS_SERIES (702), vehicle class Other
      all other subfolders             → IN_SPECIALTY_SERIES (701)

    Category routing:
      in-schools         → School (95%)
      in-veteran         → Military / Veteran (95%)
      in-first-responder → First Responder (95%)
      in-fraternal       → Fraternal / Civic (88%)
      in-outdoors        → Conservation / Environment (90%)
      in-sports          → Sports Team (90%); 'environmental' → Conservation; keyword rules apply
      in-non-passenger   → Other / Specialty (78%); vehicle class Other
      in-standard-issue  → year-based std-issue (95%); non-year extras → keyword overrides
      in-specialty       → IN_SPECIALTY_RULES → IN_SPECIALTY_DEFAULT

    Vehicle class:
      in-non-passenger subfolder → Other
      default → Passenger
    """
    if not stem.lower().startswith('in-'):
        return None

    core_raw = stem[3:]           # strip 'in-', preserve case
    core     = core_raw.lower()   # lowercase for matching

    vehicle_class = 'Passenger'

    # ── Non-passenger subfolder ────────────────────────────────────────────────
    if subfolder == 'in-non-passenger':
        vehicle_class    = 'Other'
        series           = IN_NON_PASS_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 78

    # ── Standard-issue subfolder ───────────────────────────────────────────────
    elif subfolder == 'in-standard-issue':
        if '2017' in core:
            series = IN_STD_2017_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif '2013' in core:
            series = IN_STD_2013_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif '2008' in core:
            series = IN_STD_2008_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif '2003' in core:
            series = IN_STD_2003_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
            # Filename has no descriptor — force the Farm name
            core_raw = 'Standard Issue 2003 Farm'
            core     = core_raw.lower()
        elif '1998' in core:
            series = IN_STD_1998_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'amateur-radio' in core:
            series = IN_STD_2017_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disability' in core or 'disabled' in core:
            series = IN_STD_2017_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif 'historic' in core:
            series = IN_STD_2017_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            series = IN_STD_2017_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 90

    # ── Direct subfolder → category mappings ──────────────────────────────────
    elif subfolder == 'in-schools':
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'in-veteran':
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'in-first-responder':
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'in-fraternal':
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'in-outdoors':
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'in-sports':
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = IN_SPORTS_DEFAULT
        for keywords, cid, conf in IN_SPORTS_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    else:  # in-specialty (and any unexpected subfolder)
        series = IN_SPECIALTY_SERIES
        cat_id, cat_conf = IN_SPECIALTY_DEFAULT
        for keywords, cid, conf in IN_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    # Apply name overrides for known acronym / formatting issues (stem has no extension)
    if stem.lower() in IN_NAME_OVERRIDES:
        name_text = IN_NAME_OVERRIDES[stem.lower()]
    else:
        name_text = to_title(core_raw)
    plate_name = f'IN - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── KS parser ─────────────────────────────────────────────────────────────────
def parse_ks(stem: str, subfolder: str, actual_filename: str):
    """Parse a single KS (Kansas) plate image across 8 subfolders.

    Series routing:
      ks-standard-issue:
        personalized-issue-2020-* → KS_PERS_2020_SERIES (705)
        personalized-issue-2025-* → KS_PERS_2025_SERIES (707)
        standard-issue-2007-*     → KS_STD_2007_SERIES  (703)
        standard-issue-2024-*     → KS_STD_2025_SERIES  (706)
        standard-issue-2019-*     → KS_STD_2019_SERIES  (704)
        antique-*                 → KS_STD_2019_SERIES  (704)
        blackout                  → KS_SPECIALTY_SERIES (708)
        default                   → KS_STD_2019_SERIES  (704)
      ks-non-passenger  → KS_NON_PASS_SERIES (709), vehicle class Other
      all other folders → KS_SPECIALTY_SERIES (708)

    Category routing:
      ks-first-responder → First Responder (95%); honor-the-fallen → Other/Specialty (72%)
      ks-fraternal       → Fraternal / Civic (88%)
      ks-outdoors        → Conservation / Environment (90%)
      ks-schools         → School (95%)
      ks-sports          → Sports Team (90%)
      ks-veteran         → Military / Veteran (95%); disabled-veteran → Disabled (90%)
      ks-non-passenger   → dealer→ Dealer/Manufacturer (88%); city/official/govt→ Government/Exempt (82%); default Other/Specialty (72%)
      ks-specialty       → keyword rules (health, ag, arts, historical, default Other/Specialty)
      ks-standard-issue  → keyword overrides (radio, disabled, antique, other-subtypes)

    Vehicle class:
      ks-non-passenger  → Other
      -motorcycle stem  → Motorcycle
      default           → Passenger
    """
    if not stem.lower().startswith('ks-'):
        return None

    # ── Motorcycle detection (before any other logic) ──────────────────────────
    core_raw = stem[3:]          # strip 'ks-', preserve case
    core     = core_raw.lower() # lowercase for matching

    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    # ── Non-passenger subfolder ────────────────────────────────────────────────
    if subfolder == 'ks-non-passenger':
        vehicle_class    = 'Other'
        series           = KS_NON_PASS_SERIES
        if 'dealer' in core:
            cat_id, cat_conf = CAT['Dealer / Manufacturer'], 88
        elif any(kw in core for kw in ('city', 'official', 'foreign-organization', 'kcc', 'motor-carrier', 'pwr-commercial')):
            cat_id, cat_conf = CAT['Government / Exempt'], 82
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── Standard-issue subfolder ───────────────────────────────────────────────
    elif subfolder == 'ks-standard-issue':
        # Series routing by keyword (most specific first)
        if 'personalized-issue-2020' in core:
            series = KS_PERS_2020_SERIES
        elif 'personalized-issue-2025' in core:
            series = KS_PERS_2025_SERIES
        elif 'standard-issue-2007' in core:
            series = KS_STD_2007_SERIES
        elif 'standard-issue-2024' in core:
            series = KS_STD_2025_SERIES
        elif 'standard-issue-2019' in core:
            series = KS_STD_2019_SERIES
        elif 'antique' in core:
            series = KS_STD_2019_SERIES
        elif 'blackout' in core:
            series = KS_SPECIALTY_SERIES
        else:
            series = KS_STD_2019_SERIES

        # Category routing
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disabled' in core or 'diabled' in core:  # typo in ks-standard-issue-2019-diabled.png
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif 'antique-blue' in core or 'antique-embossed' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core for kw in ('antique-vehicle', 'rental-car', 'special-interest', 'street-rod', 'blackout')):
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    # ── Direct subfolder → category mappings ──────────────────────────────────
    elif subfolder == 'ks-first-responder':
        series = KS_SPECIALTY_SERIES
        if 'honor-the-fallen' in core:
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:
            cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'ks-fraternal':
        series = KS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'ks-outdoors':
        series = KS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'ks-schools':
        series = KS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'ks-sports':
        series = KS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'ks-veteran':
        series = KS_SPECIALTY_SERIES
        if 'disabled-veteran' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    else:  # ks-specialty (and any unexpected subfolder)
        series = KS_SPECIALTY_SERIES
        if any(kw in core for kw in ('autism', 'cancer', 'bradens-hope', 'childrens-trust', 'choose-life', 'donate-life', 'downs-syndrome')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('4h-foundation', 'agriculture-in-the-classroom', 'horse-council')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif 'support-the-arts' in core:
            cat_id, cat_conf = CAT['Arts / Culture'], 88
        elif 'eisenhower-foundation' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    KS_NAME_OVERRIDES = {
        'ks-standard-issue-2019-diabled':         'Standard Issue 2019 Disabled',
        'ks-standard-issue-2019-special-interest4': 'Standard Issue 2019 Special Interest',
    }
    override_key = f'ks-{core_raw.lower()}'
    if override_key in KS_NAME_OVERRIDES:
        name_text = KS_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'KS - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── LA parser ────────────────────────────────────────────────────────────────
def parse_la(stem: str, subfolder: str, actual_filename: str):
    """Parse a single LA (Louisiana) plate image across 9 subfolders.

    Series routing:
      la-standard-issue:
        standard-issue-2025-* → LA_STD_2025_SERIES (710)
        standard-issue-2005-* → LA_STD_2005_SERIES (711)
        amateur-radio, antique, street-cruiser, street-rod → LA_STD_2025_SERIES (710)
      la-non-passenger  → LA_NON_PASS_SERIES (712)
      all other folders → LA_SPECIALTY_SERIES (713)

    Category routing:
      la-first-responder → First Responder (95%)
      la-fraternal       → Fraternal / Civic (88%)
      la-outdoors        → Conservation / Environment (90%)
      la-schools         → School (95%)
      la-sports          → Sports Team (90%)
      la-veteran         → Military / Veteran (95%); disabled → Disabled (90%)
      la-non-passenger   → Other / Specialty (72%)
      la-specialty       → keyword-based (health, ag, arts, fraternal, historical, school, default)
      la-standard-issue  → Standard Issue (95%) or Radio/Amateur Radio, Historical, Other/Specialty
    """
    if not stem.lower().startswith('la-'):
        return None

    # ── Motorcycle detection ──────────────────────────────────────────────────
    core_raw = stem[3:]          # strip 'la-'
    core     = core_raw.lower()

    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    # ── Non-passenger subfolder ───────────────────────────────────────────────
    if subfolder == 'la-non-passenger':
        vehicle_class    = 'Other'
        series           = LA_NON_PASS_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── Standard-issue subfolder ──────────────────────────────────────────────
    elif subfolder == 'la-standard-issue':
        if 'standard-issue-2025' in core:
            series           = LA_STD_2025_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'standard-issue-2005' in core:
            series           = LA_STD_2005_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'amateur-radio' in core:
            series           = LA_STD_2025_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'antique' in core:
            series           = LA_STD_2025_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core for kw in ('street-cruiser', 'street-rod')):
            series           = LA_STD_2025_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:
            series           = LA_STD_2025_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95

    # ── Direct subfolder → category mappings ─────────────────────────────────
    elif subfolder == 'la-first-responder':
        series = LA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'la-fraternal':
        series = LA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'la-outdoors':
        series = LA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'la-schools':
        series = LA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'la-sports':
        series = LA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'la-veteran':
        series = LA_SPECIALTY_SERIES
        if 'disabled-veteran' in core or '100-disabled-veteran' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    else:  # la-specialty and any unexpected subfolder
        series = LA_SPECIALTY_SERIES
        if any(kw in core for kw in ('autism', 'cancer', 'awarness', 'child-safety',
                                      'coalition-against-violence', 'down-syndrome',
                                      'feeding-hope', 'aids-advocacy', 'lung-cancer',
                                      'motorcycle-awareness', 'organ-donation',
                                      'unlocking-autism')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('4h', 'agricultural', 'agriculture',
                                        'cattlemen', 'seafood')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif any(kw in core for kw in ('laissez-les-art', 'wwoz', 'i-m-cajun',
                                        'i-m-creole', 'chez-nous', 'juneteenth',
                                        '300th-anniversary')):
            cat_id, cat_conf = CAT['Arts / Culture'], 88
        elif any(kw in core for kw in ('boy-scouts', 'girl-scout', 'grotto',
                                        'camp-woodmen')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 88
        elif any(kw in core for kw in ('sons-of-confederate', 'jefferson-parish-bicentennial',
                                        'charles-dunbar')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core for kw in ('educator', 'math-science-arts', 'helping-schools')):
            cat_id, cat_conf = CAT['School'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    LA_NAME_OVERRIDES = {
        'la-4h':                              '4-H',
        'la-breast-cancer-awarness':          'Breast Cancer Awareness',
        'la-c-e-byrd-high-school':            'CE Byrd High School',
        'la-caddo-parish-magnet-h-school':    'Caddo Parish Magnet High School',
        'la-globalwaronterrorism':            'Global War on Terrorism',
        'la-i-m-cajun-and-proud':             "I'm Cajun and Proud",
        'la-i-m-creole-and-proud':            "I'm Creole and Proud",
        'la-jc-christian':                    'JC Christian',
        'la-k9s4cops':                        'K9s4Cops',
        'la-lsu':                             'LSU',
        'la-lsu-alexandria':                  'LSU Alexandria',
        'la-lsu-baseball-national-chanpions': 'LSU Baseball National Champions',
        'la-lsu-eunice':                      'LSU Eunice',
        'la-lsu-national-champs-2019':        'LSU National Champions 2019',
        'la-lsu-school-of-dentistry':         'LSU School of Dentistry',
        'la-lsu-shreveport':                  'LSU Shreveport',
        'la-lsu-womens-basketball':           "LSU Women's Basketball",
        'la-m-w-prince-hall':                 'M.W. Prince Hall',
        'la-mcdonogh-high-school':            'McDonogh High School',
        'la-mckinley-senior-high-school':     'McKinley Senior High School',
        'la-mcneese-state-university':        'McNeese State University',
        'la-nergystate':                      'Energy State',
        'la-seymore-dfair':                   'Seymour D. Fair',
        'la-w-monroe-hs':                     'West Monroe High School',
        'la-water-wastewater-operato':        'Water Wastewater Operator',
        'la-world-war-ii-veteran':            'World War II Veteran',
        'la-wwoz-guardians-of-the-groove':    'WWOZ Guardians of the Groove',
    }
    override_key = f'la-{core_raw.lower()}'
    if override_key in LA_NAME_OVERRIDES:
        name_text = LA_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'LA - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MA parser ────────────────────────────────────────────────────────────────
def parse_ma(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MA (Massachusetts) plate image across 9 subfolders.

    Series routing:
      ma-standard-issue:
        standard-issue-1993-* → MA_STD_SERIES (714)
        all other files       → MA_SPECIALTY_SERIES (715)
      ma-non-passenger → MA_NON_PASS_SERIES (716)
      all other folders → MA_SPECIALTY_SERIES (715)

    Note: subfolder may be spelled 'ma-shcools' (typo) — treated as 'ma-schools'.
    """
    if not stem.lower().startswith('ma-'):
        return None

    core_raw = stem[3:]          # strip 'ma-'
    core     = core_raw.lower()

    # No motorcycle variants in MA but keep detection for safety
    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    # ── Non-passenger subfolder ──────────────────────────────────────────────
    if subfolder == 'ma-non-passenger':
        vehicle_class    = 'Other'
        series           = MA_NON_PASS_SERIES
        if any(kw in core for kw in ('governors-council', 'house', 'senate',
                                      'united-states-congress', 'united-states-senate')):
            cat_id, cat_conf = CAT['Government / Exempt'], 82
        elif 'foreign-organization' in core or 'honorary-consular' in core:
            cat_id, cat_conf = CAT['Government / Exempt'], 80
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── Standard-issue subfolder ──────────────────────────────────────────────
    elif subfolder == 'ma-standard-issue':
        if 'standard-issue-1993' in core:
            series           = MA_STD_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'ham-operator' in core or 'amateur' in core:
            series           = MA_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disability' in core or 'disabled-veteran' in core:
            series           = MA_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif 'antique' in core:
            series           = MA_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'independence-250' in core:
            series           = MA_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'electric-vehicle' in core:
            series           = MA_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 72
        else:  # cape-ann, united-we-stand, welcome-home, etc.
            series           = MA_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── Direct subfolder → category mappings ─────────────────────────────────
    elif subfolder == 'ma-first-responder':
        series = MA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'ma-fraternal':
        series = MA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'ma-outdoors':
        series = MA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder in ('ma-schools', 'ma-shcools'):  # handle folder typo
        series = MA_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'ma-sports':
        series = MA_SPECIALTY_SERIES
        if any(kw in core for kw in ('jimmy-fund',)):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        else:
            cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'ma-veteran':
        series = MA_SPECIALTY_SERIES
        if any(kw in core for kw in ('disabled', 'disability')):
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    else:  # ma-specialty and unexpected subfolders
        series = MA_SPECIALTY_SERIES
        if any(kw in core for kw in ('als', 'cancer', 'overdose', 'invest-in-children',
                                      'registered-nurse', 'health')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('firefighters-memorial', 'state-police')):
            cat_id, cat_conf = CAT['First Responder'], 88
        elif any(kw in core for kw in ('dr-seuss', 'animal-coalition')):
            cat_id, cat_conf = CAT['Arts / Culture'], 88
        elif 'fresh-and-local' in core:
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif 'plymouth-400' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    MA_NAME_OVERRIDES = {
        'ma-als-one':                                   'ALS One',
        'ma-dr-seuss':                                  'Dr. Seuss',
        'ma-limited-use-vehicle-luv':                   'Limited Use Vehicle (LUV)',
        'ma-martha-s-vineyard':                         "Martha's Vineyard",
        'ma-medical-doctor-md':                         'Medical Doctor (MD)',
        'ma-news-photographer-plates':                  'News Photographer',
        'ma-red-sox-jimmy-fund-v1':                     'Red Sox Jimmy Fund v1',
        'ma-red-sox-jimmy-fund-v2':                     'Red Sox Jimmy Fund v2',
        'ma-state-police-association-of-massachusetts-v1': 'State Police Association of Massachusetts v1',
        'ma-state-police-association-of-massachusetts-v2': 'State Police Association of Massachusetts v2',
        'ma-umass':                                     'UMass',
        'ma-united-states-congress':                    'United States Congress',
        'ma-united-states-senate':                      'United States Senate',
    }
    override_key = f'ma-{core_raw.lower()}'
    if override_key in MA_NAME_OVERRIDES:
        name_text = MA_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MA - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MB parser ─────────────────────────────────────────────────────────────────
def parse_mb(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MB (Manitoba) plate image across 7 subfolders.

    Series routing:
      mb-standard-issue:
        standard-issue-1997-*  → MB_STD_SERIES (717)
        amateur-radio          → MB_SPECIALTY_SERIES (718)
      all other folders        → MB_SPECIALTY_SERIES (718)
      mb-non-passenger         → MB_SPECIALTY_SERIES (718), vehicle class Other

    Category routing:
      mb-non-passenger  → Other / Specialty (72%), vehicle Other
      mb-outdoors       → Conservation / Environment (90%)
      mb-schools        → School (95%)
      mb-sports         → Sports Team (90%)
      mb-veteran        → Military / Veteran (95%)
      mb-specialty      → keyword-based (health, arts, default)
      mb-standard-issue → Standard Issue (95%) or Radio / Amateur Radio (95%)
    """
    if not stem.lower().startswith('mb-'):
        return None

    core_raw = stem[3:]
    core     = core_raw.lower()

    # ── Motorcycle detection ────────────────────────────────────────────────
    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    # ── Non-passenger subfolder ─────────────────────────────────────────────
    if subfolder == 'mb-non-passenger':
        vehicle_class    = 'Other'
        series           = MB_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    # ── Standard-issue subfolder ────────────────────────────────────────────
    elif subfolder == 'mb-standard-issue':
        if 'amateur-radio' in core:
            series           = MB_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        else:
            series           = MB_STD_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95

    # ── Direct subfolder → category mappings ───────────────────────────────
    elif subfolder == 'mb-outdoors':
        series = MB_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'mb-schools':
        series = MB_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'mb-sports':
        series = MB_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'mb-veteran':
        series = MB_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    else:  # mb-specialty and unexpected
        series = MB_SPECIALTY_SERIES
        if any(kw in core for kw in ('cancer', 'mmiwg', 'prostate', 'warriors')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('humane', 'snoman')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    MB_NAME_OVERRIDES = {
        'mb-commerical':                         'Commercial',
        'mb-mmiwg-red-dress':                    'MMIWG Red Dress',
        'mb-mmiwg-red-hand':                     'MMIWG Red Hand',
        'mb-university-of-winnepeg':             'University of Winnipeg',
        'mb-winnepeg-humane-society':            'Winnipeg Humane Society',
        'mb-winnepeg-jets-fuelled-by-passion':   'Winnipeg Jets Fuelled by Passion',
        'mb-winnepeg-jets-honor-the-past':       'Winnipeg Jets Honor the Past',
    }
    override_key = f'mb-{core_raw.lower()}'
    if override_key in MB_NAME_OVERRIDES:
        name_text = MB_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MB - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MD parser ────────────────────────────────────────────────────────────────
def parse_md(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MD (Maryland) plate image across 9 subfolders (~982 files).

    Series routing:
      md-standard-issue / 2016 or flag → MD_STD_2016_SERIES (719)
      md-standard-issue / 1986         → MD_STD_1986_SERIES (720)
      all other subfolders             → MD_SPECIALTY_SERIES (721)

    Motorcycle detection:
      Handles full -motorcycle suffix plus GIF-truncated variants:
      -motorcycl, -mot (len>=50), -mo (len>=55)

    Trailing-hyphen truncation artifacts are stripped before naming.
    """
    if not stem.lower().startswith('md-'):
        return None

    core_raw = stem[3:]
    core     = core_raw.lower()

    # ── Strip trailing-hyphen truncation artifact ──────────────────────────
    if core_raw.endswith('-'):
        core_raw = core_raw.rstrip('-')
        core     = core_raw.lower()

    # ── Motorcycle detection (full + GIF-truncated variants) ────────────────
    is_moto = False
    if core.endswith('-motorcycle'):
        is_moto  = True
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
    elif core.endswith('-motorcycl'):        # truncated '-motorcycle'
        is_moto  = True
        core_raw = re.sub(r'-motorcycl$', '', core_raw, flags=re.IGNORECASE)
    elif core.endswith('-mot') and len(core) >= 50:
        is_moto  = True
        core_raw = re.sub(r'-mot$', '', core_raw, flags=re.IGNORECASE)
    elif core.endswith('-mo') and len(core) >= 55:
        is_moto  = True
        core_raw = re.sub(r'-mo$', '', core_raw, flags=re.IGNORECASE)
    core          = core_raw.lower()
    vehicle_class = 'Motorcycle' if is_moto else 'Passenger'
    moto_suffix   = ' - Motorcycle' if is_moto else ''

    # ── Standard-issue subfolder ──────────────────────────────────────────────
    if subfolder == 'md-standard-issue':
        if '2016' in core or 'flag' in core:
            series           = MD_STD_2016_SERIES
        else:
            series           = MD_STD_1986_SERIES
        cat_id, cat_conf = CAT['Standard Issue'], 95

    # ── Direct subfolder → category mappings ─────────────────────────────────
    elif subfolder == 'md-first-responders':
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'md-fraternal':
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'md-outdoors':
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'md-schools':
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'md-sports':
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'md-veteran':
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'md-non-passenger':
        vehicle_class    = 'Other'
        series           = MD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    else:  # md-specialty and unexpected
        series = MD_SPECIALTY_SERIES
        if any(kw in core for kw in ('cancer', 'als', 'autism', 'donate-life', 'hospital',
                                      'medical', 'nurse', 'cure', 'overdose', 'ovarian',
                                      'ulman', 'sisters-surviving', 'pink-wishes',
                                      'down-syndrome', 'family-resource', 'cool-kids',
                                      'guiding-eyes', 'hatzalah', 'mount-washington')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('rescue', 'humane', 'spay-neuter', 'animal',
                                        'greyhound', 'greyt', 'retriever',
                                        'chesapeake-and-coastal', 'izaak-walton',
                                        'community-cats', 'senior-dog', 'oldies-but',
                                        'aussie-rescue', 'mid-atlantic-german-shepherd',
                                        'mid-atlantic-pug')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 85
        elif any(kw in core for kw in ('symphony', 'blues-society', 'rock-opera',
                                        'harbor-city-music', 'federation-of-art',
                                        'public-television', 'country-pride-dancers',
                                        'upper-chesapeake-chorus', 'pride-of-baltimore',
                                        'baltimore-blues', 'choptank-electric')):
            cat_id, cat_conf = CAT['Arts / Culture'], 85
        elif any(kw in core for kw in ('church', 'temple', 'baptist', 'episcopal',
                                        'methodist', 'calvary', 'faith-united',
                                        'grace-bible', 'missionary', 'chapel',
                                        'tabernacle', 'christian-center',
                                        'believers-worship', 'rooted-bible',
                                        'transformation-church', 'triumphant',
                                        'true-buddha', 'spirit-of-faith',
                                        'last-boat-of-salvation', 'diocese',
                                        'united-church-of-christ', 'franciscan',
                                        'family-life-ministries', 'bread-of-life',
                                        'greater-harvest', 'little-ark',
                                        'maple-springs', 'pleasant-grove',
                                        'first-baptist', 'new-shiloh',
                                        'queen-s-chapel', 'rosedale-baptist',
                                        'washington-district-church')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 78
        elif any(kw in core for kw in ('museum', 'historical', 'heritage', 'history',
                                        'society-of-mayflower', 'sons-of-union',
                                        'war-of-1812', 'streetcar', 'railroad',
                                        'railway', 'vintage', '1910', 'archeological',
                                        'glen-l-martin', 'hubble', 'space-telescope',
                                        'james-webb', 'nasa', 'next-generation-space',
                                        'project-liberty', 'david-taylor',
                                        'historic-st-marys', 'port-deposit',
                                        'society-of-senate', 'north-south-skirmish',
                                        'old-line-garrison', 'queen-anne')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif any(kw in core for kw in ('agriculture', 'farmers', 'arborist',
                                        'agricultural-fair', 'farm-bureau')):
            cat_id, cat_conf = CAT['Agricultural'], 85
        elif 'protect-the-chesapeake-disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    MD_NAME_OVERRIDES = {
        # Truncated non-motorcycle names
        'md-american-federation-of-state-county-and-municipal-employees': 'American Federation of State County and Municipal Employees',
        'md-baltimore-county-fire-department-chief-officers-association':  'Baltimore County Fire Department Chief Officers Association',
        'md-baltimore-area-alumni-association-inc-of-alpha-phi-omega-fra': 'Baltimore Area Alumni Association Inc of Alpha Phi Omega Fraternity',
        'md-middle-atlantic-section-of-the-professional-golfers-associat': 'Middle Atlantic Section of the Professional Golfers Association',
        # Abbreviations / special characters
        'md-almas-temple-a-a-o-n-m-s':                             'Almas Temple A.A.O.N.M.S.',
        'md-b-o-railroad-museum':                                  'B&O Railroad Museum',
        'md-boumi-temple-a-a-o-n-m-s':                             'Boumi Temple A.A.O.N.M.S.',
        'md-bwi-business-partnership':                             'BWI Business Partnership',
        'md-dc-vote':                                              'DC Vote',
        'md-dfc-jason-c-schwenz-foundation-inc':                   'DFC Jason C. Schwenz Foundation Inc',
        'md-fbi-national-academy-associates':                      'FBI National Academy Associates',
        'md-g-burg-vettes-inc':                                    'G-Burg Vettes Inc',
        'md-groove-phi-groove-sfi':                                'Groove Phi Groove SFI',
        'md-ibew-local-union-1900':                                'IBEW Local Union 1900',
        'md-isso-international-swaminarayan-satsang-organization':  'ISSO International Swaminarayan Satsang Organization',
        'md-m-w-zerubbabel-grand-lodge':                           'M.W. Zerubbabel Grand Lodge',
        'md-mddc-society-for-respiratory-care':                    'MDDC Society for Respiratory Care',
        'md-mit-club-of-washington':                               'MIT Club of Washington',
        'md-most-worshipful-prince-hall-grand-lodge-f-a-m':        'Most Worshipful Prince Hall Grand Lodge F.A.M.',
        'md-nasa-goddard-employees-welfare-association':           'NASA Goddard Employees Welfare Association',
        'md-nasa-wallops-flight-facility':                         'NASA Wallops Flight Facility',
        'md-s-p-e-b-s-q-s-a-inc':                                 'SPEBSQSA Inc',
        'md-s-t-kendall-lodge-153':                                'S.T. Kendall Lodge 153',
        'md-swing-phi-swing-s-f-i':                                'Swing Phi Swing SFI',
        'md-tri-state-association-i-b-p-order-of-elks-of-the-world': 'Tri-State Association IBP Order of Elks of the World',
        'md-u-s-masters-swimming':                                 'U.S. Masters Swimming',
        'md-ufcw-local-400':                                       'UFCW Local 400',
        'md-usafa-parents-association-national-capitol-area':      'USAFA Parents Association National Capitol Area',
        'md-us-public-health-service':                             'US Public Health Service',
        # Typos in source filenames
        'md-maryland-casa-association-child-adovcate':             'Maryland CASA Association Child Advocate',
        'md-maryland-federaton-of-business-and-professional-women-s-club': "Maryland Federation of Business and Professional Women's Club",
        # Apostrophe cases
        'md-grand-commandery-of-maryland-s-knights-templar':       "Grand Commandery of Maryland's Knights Templar",
        'md-hill-s-angels-gymnastics-team-inc':                    "Hill's Angels Gymnastics Team Inc",
        'md-maryland-s-eastern-shore':                             "Maryland's Eastern Shore",
        'md-maryland-saltwater-sportfishermen-s-association-inc':  "Maryland Saltwater Sportfishermen's Association Inc",
        'md-maryland-state-firemen-s-association':                 "Maryland State Firemen's Association",
        'md-maryland-watermens-association-inc':                   "Maryland Watermen's Association Inc",
        'md-o-conor-piper-flynn-recreational-social-club-inc':     "O'Conor Piper Flynn Recreational Social Club Inc",
        'md-prince-george-s-county-crime-solvers-inc':             "Prince George's County Crime Solvers Inc",
        'md-protect-the-chesapeake-disabled':                      'Protect the Chesapeake - Disabled',
        'md-queen-anne-s-co-300th-anniversary-committee':          "Queen Anne's Co. 300th Anniversary Committee",
        'md-queen-s-chapel-united-methodist-church':               "Queen's Chapel United Methodist Church",
        'md-st-andrew-s-society-of-baltimore':                     "St. Andrew's Society of Baltimore",
        'md-st-mary-s-county-als-unit':                            "St. Mary's County ALS Unit",
        'md-st-mary-s-county-tennis-association-inc':              "St. Mary's County Tennis Association Inc",
        'md-the-maryland-4-h-foundation-inc':                      'Maryland 4-H Foundation Inc',
        # Misc
        'md-cal-ripken-sr-foundation':                             'Cal Ripken Sr. Foundation',
        'md-1910-vintage':                                         '1910 Vintage',
        'md-howard-university-alumni-chapter-of-prince-george-s-county': "Howard University Alumni Chapter of Prince George's County",
        'md-prince-george-s-county-professional-firefighters-association': "Prince George's County Professional Firefighters Association",
        'md-retired-dc-police-firemen':                            'Retired DC Police Firemen',
        'md-baltimore-county-fire-fighters-association-local-no-1311': 'Baltimore County Fire Fighters Association Local No. 1311',
    }
    override_key = f'md-{core_raw.lower()}'
    if override_key in MD_NAME_OVERRIDES:
        name_text = MD_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MD - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── ME parser ─────────────────────────────────────────────────────────────────
def parse_me(stem: str, subfolder: str, actual_filename: str):
    """Parse a single ME (Maine) plate image across 9 subfolders.

    Series routing:
      me-standard-issue:
        '2025' in filename        → ME_STD_2025_SERIES (723)
        'amputee' in filename     → ME_VETERAN_SERIES  (725)
        'disability' in filename  → ME_SPECIALTY_SERIES (724)
        antique                   → ME_STD_1999_SERIES (722), Historical
        autocycle / moped         → ME_STD_1999_SERIES (722), Other class
        everything else           → ME_STD_1999_SERIES (722)
      me-veteran                  → ME_VETERAN_SERIES  (725)
      me-non-passenger            → ME_STD_1999_SERIES (722)  [not yet updated to 2025]
      all other subfolders        → ME_SPECIALTY_SERIES (724)

    Veteran disabled suffix:
      'veteran-*-disabled' filenames: '-disabled' stripped, '(Disabled)' appended to name.

    Duplicates:
      Files with a space in the stem (e.g. 'me-purple-heart-motorcycle (2)') are skipped.
    """
    if not stem.lower().startswith('me-'):
        return None

    # Skip duplicates (space in filename = '(2)' copy)
    if ' ' in stem:
        return None

    core_raw = stem[3:]
    core     = core_raw.lower()

    # ── Motorcycle detection ──────────────────────────────────────────────────
    is_moto = False
    if core == 'motorcycle' or core.endswith('-motorcycle'):
        is_moto  = True
        core_raw = re.sub(r'-?motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
    vehicle_class = 'Motorcycle' if is_moto else 'Passenger'
    moto_suffix   = ' - Motorcycle' if is_moto else ''

    # ── Veteran disabled-variant detection (only 'veteran-*-disabled') ────────
    is_disabled_variant = False
    if (subfolder == 'me-veteran'
            and core.endswith('-disabled')
            and core.startswith('veteran-')):
        is_disabled_variant = True
        core_raw = re.sub(r'-disabled$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
    disabled_suffix = ' (Disabled)' if is_disabled_variant else ''

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'me-standard-issue':
        if 'amputee' in core:
            series           = ME_VETERAN_SERIES
            cat_id, cat_conf = CAT['Military / Veteran'], 95
        elif 'disability' in core:
            series           = ME_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif '2025' in core:
            series           = ME_STD_2025_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'antique' in core:
            series           = ME_STD_1999_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        elif core in ('autocycle', 'moped'):
            series           = ME_STD_1999_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80
            vehicle_class    = 'Other'
        elif core in ('street-rod', 'custom-vehicle'):
            series           = ME_STD_1999_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        else:
            series           = ME_STD_1999_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif subfolder == 'me-veteran':
        series           = ME_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'me-non-passenger':
        series           = ME_STD_1999_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 80
        vehicle_class    = 'Other'

    elif subfolder == 'me-first responder':
        series           = ME_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'me-outdoors':
        series           = ME_SPECIALTY_SERIES
        if 'agriculture' in core:
            cat_id, cat_conf = CAT['Agricultural'], 88
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'me-schools':
        series           = ME_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'me-sports':
        series           = ME_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'me-fraternal':
        series           = ME_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    else:  # me-specialty and unexpected
        series = ME_SPECIALTY_SERIES
        if any(kw in core for kw in ('cancer', 'breast', 'barbara-bush', 'hospital')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif 'animal' in core:
            cat_id, cat_conf = CAT['Conservation / Environment'], 85
        elif 'support-troops' in core:
            cat_id, cat_conf = CAT['Military / Veteran'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    ME_NAME_OVERRIDES = {
        # Standard-issue subfolder
        'me-':                                          'Standard Issue',       # me-motorcycle.png (bare stem after stripping)
        'me-antique':                                   'Antique Auto',         # me-antique-motorcycle.png (pairs with Antique Auto)
        'me-amputee-loss-of-use-of-limb-s-or-blind-veteran': 'Amputee / Loss of Use of Limb(s) or Blind Veteran',
        # Non-passenger subfolder
        'me-agriculture-commerical':            'Agriculture Commercial',   # typo in source
        'me-motorhome-disabled':                'Motor Home - Disabled',
        'me-motor-home':                        'Motor Home',
        'me-trailer-long-term':                 'Trailer - Long Term',
        # Veteran subfolder
        'me-disability-special-veteran-decal':  'Disability Special Veteran - Decal',
        'me-disabled-veteran-parking-with-icon':'Disabled Veteran Parking (with icon)',
        'me-gold-star-family-gold':             'Gold Star Family (Gold)',
        'me-gold-star-family-purple':           'Gold Star Family (Purple)',
        'me-pearl-harbor-survivor-plate':       'Pearl Harbor Survivor',
        'me-special-veteran-plate':             'Special Veteran',
        'me-special-veteran-plate-decal':       'Special Veteran - Decal',
        # Veteran (World War II casing)
        'me-veteran-world-war-ii':              'Veteran World War II',
        # Specialty subfolder
        'me-barbara-bush-childrens-hospital':   "Barbara Bush Children's Hospital",
        'me-support-troops':                    'Support Our Troops',
        'me-wabanaki-recognition-plate':        'Wabanaki Recognition',
    }
    override_key = f'me-{core_raw.lower()}'
    if override_key in ME_NAME_OVERRIDES:
        name_text = ME_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'ME - {name_text}{moto_suffix}{disabled_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── IL parser ─────────────────────────────────────────────────────────────────
def parse_il(stem: str, subfolder: str, actual_filename: str):
    """Parse a single IL (Illinois) plate image across 9 subfolders.

    Series routing:
      il-standard-issue:
        motorcycle-ta-trailer          → IL_NP_SERIES (694), Other class
        disability keywords            → IL_STD_SERIES (693), Disabled/Accessibility
        antique keywords               → IL_STD_SERIES (693), Historical
        specialty (electric, rec, etc) → IL_SPECIALTY_SERIES (695)
        all others                     → IL_STD_SERIES (693), Standard Issue
      il-veteran                       → IL_VETERAN_SERIES (727)
      il-non-passenger                 → IL_NP_SERIES (694), Other class
        weight-based names formatted as 'Type (lo-hi lbs)'
      all other subfolders             → IL_SPECIALTY_SERIES (695)
    """
    if not stem.lower().startswith('il-'):
        return None

    core_raw = stem[3:]
    core     = core_raw.lower()

    # ── Motorcycle detection ──────────────────────────────────────────────────
    is_moto = False
    if core == 'motorcycle' or core.endswith('-motorcycle'):
        is_moto  = True
        core_raw = re.sub(r'-?motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
    vehicle_class = 'Motorcycle' if is_moto else 'Passenger'
    moto_suffix   = ' - Motorcycle' if is_moto else ''

    # ── Standard-issue subfolder ─────────────────────────────────────────────
    if subfolder == 'il-standard-issue':
        if core == 'motorcycle-ta-trailer':
            series        = IL_NP_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80
            vehicle_class = 'Other'
        elif any(kw in core for kw in ('disabled', 'disabilities', 'hearing-impaired')):
            series        = IL_STD_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif 'antique' in core:
            series        = IL_STD_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        elif any(kw in core for kw in ('electric-vehicle', 'recreational',
                                        'motorscooter', 'amateur-radio',
                                        'tinted-windows', 'autocycle')):
            series        = IL_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 75
        else:  # 2017-standard-issue, bare motorcycle
            series        = IL_STD_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        # Autocycles are a non-standard vehicle class
        if 'autocycle' in core:
            vehicle_class = 'Other'
        if 'motorscooter' in core:
            vehicle_class = 'Other'

    # ── Veteran subfolder → series 727 ────────────────────────────────────
    elif subfolder == 'il-veteran':
        series           = IL_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    # ── Non-passenger subfolder ─────────────────────────────────────────────
    elif subfolder == 'il-non-passenger':
        series        = IL_NP_SERIES
        vehicle_class = 'Other'
        if 'farm' in core:
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif 'president' in core:
            cat_id, cat_conf = CAT['Government / Exempt'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    # ── Direct subfolder → category mappings ─────────────────────────────────
    elif subfolder == 'il-first-responder':
        series           = IL_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'il-fraternal':
        series           = IL_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'il-outdoors':
        series           = IL_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'il-schools':
        series           = IL_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'il-sports':
        series           = IL_SPECIALTY_SERIES
        if core == 'share-the-road':
            cat_id, cat_conf = CAT['Conservation / Environment'], 88
        else:
            cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # il-specialty and unexpected
        series = IL_SPECIALTY_SERIES
        if any(kw in core for kw in ('cancer', 'alzheimer', 'autism', 'mammogram',
                                      'organ-donor', 'hospice', 'nurses', 'ovarian')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ('america-remembers', 'michigan-canal', 'route-66')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core for kw in ('eagle-scout', 'rotary', 'teamsters',
                                        'sheet-metal-workers')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        elif 'saluting-agriculture' in core:
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif 'support-our-troops' in core:
            cat_id, cat_conf = CAT['Military / Veteran'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    # ── Non-passenger weight-name formatter ───────────────────────────────────
    def commafy(s): return s.replace('-', ',')

    np_name = None
    if subfolder == 'il-non-passenger':
        # flat-weight-truck-class-X: two numbers with no 'lbs-to' separator
        m = re.match(r'^(flat-weight-truck-class-[a-z])-(\d+-\d+)-(\d+-\d+)-lbs$', core)
        if m:
            np_name = f'{to_title(m.group(1))} ({commafy(m.group(2))}-{commafy(m.group(3))} lbs)'
        if not np_name:
            # X-N-lbs-or-less
            m = re.match(r'^(.+?)-(\d+-\d+)-lbs-or-less$', core)
            if m:
                vtype = to_title(m.group(1)).replace('Trailers', 'Trailer')
                np_name = f'{vtype} ({commafy(m.group(2))} lbs or less)'
        if not np_name:
            # X-N-lbs-to/or-N-lbs (range)
            m = re.match(r'^(.+?)-(\d+-\d+)-lbs-(?:to|or)-(\d+-\d+)-lbs$', core)
            if m:
                vtype = to_title(m.group(1)).replace('Trailers', 'Trailer')
                np_name = f'{vtype} ({commafy(m.group(2))}-{commafy(m.group(3))} lbs)'

    # ── Name overrides ────────────────────────────────────────────────────────────
    IL_NAME_OVERRIDES = {
        # Standard-issue
        'il-':                                   'Standard Issue',           # bare motorcycle
        'il-2017-standard-issue':                'Standard Issue 2017',
        # Non-passenger
        'il-ta-trailer':                         'TA Trailer',
        'il-motorcycle-ta-trailer':              'Motorcycle TA Trailer',
        'il-president-of-a-village-or-incorporated-town-or-mayor':
                                                 'President of a Village / Incorporated Town / Mayor',
        # Veteran — typo fixes
        'il-submarie-veteran':                   'Submarine Veteran',
        'il-defense-distinguisted-medal':        'Defense Distinguished Medal',
        # Veteran — special formatting
        'il-pow-mia-illinois-remembers':         'POW/MIA - Illinois Remembers',
        'il-world-war-ii-veteran':               'World War II Veteran',
        'il-veteran-disabled-service-connected-iserve':
                                                 'Veteran Disabled - Service Connected (iServe)',
        # Specialty
        'il-alzheimer-s-awareness':              "Alzheimer's Awareness",
        'il-illinois-michigan-canal':            'Illinois & Michigan Canal',
        # Schools
        'il-depaul-university':                  'DePaul University',
        # Sports
        'il-chicago-sox':                        'Chicago White Sox',
    }
    override_key = f'il-{core_raw.lower()}'
    if np_name:
        name_text = np_name
    elif override_key in IL_NAME_OVERRIDES:
        name_text = IL_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'IL - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MI parser ─────────────────────────────────────────────────────────────────
def parse_mi(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MI (Michigan) plate image across 9 subfolders.

    Series routing:
      mi-standard-issue:
        mi-standard-issue-2013-pure-michigan  → MI_STD_SERIES (726), Standard Issue
        disability-plate                      → MI_STD_SERIES (726), Disabled/Accessibility
        historical                            → MI_STD_SERIES (726), Historical
        amateur-radio-operator                → MI_SPECIALTY_SERIES (731), Other
        legacy-* / water-* / mackinac-bridge-v2 → MI_ALT_SERIES (728), Historical
      mi-veteran                              → MI_VETERAN_SERIES (730)
      mi-non-passenger                        → MI_NP_SERIES (729), Other class
      all other subfolders                    → MI_SPECIALTY_SERIES (731)

    Double-extension quirk:
      mi-mackinac-bridge-v2.jpg.png — stem arrives as 'mi-mackinac-bridge-v2.jpg';
      the trailing '.jpg' is stripped from core_raw before processing.
    """
    if not stem.lower().startswith('mi-'):
        return None

    core_raw = stem[3:]
    # Strip any spurious image extension embedded in the stem (double-extension files)
    core_raw = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', core_raw, flags=re.IGNORECASE)
    core     = core_raw.lower()

    # ── Motorcycle detection ──────────────────────────────────────────────────
    is_moto = False
    if core == 'motorcycle' or core.endswith('-motorcycle'):
        is_moto  = True
        core_raw = re.sub(r'-?motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
    vehicle_class = 'Motorcycle' if is_moto else 'Passenger'
    moto_suffix   = ' - Motorcycle' if is_moto else ''

    # ── Standard-issue subfolder ─────────────────────────────────────────────
    if subfolder == 'mi-standard-issue':
        if core == 'amateur-radio-operator':
            series           = MI_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 75
        elif core == 'disability-plate':
            series           = MI_STD_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif core == 'historical':
            series           = MI_STD_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        elif (core.startswith('legacy-') or core.startswith('water-')
              or core == 'mackinac-bridge-v2'):
            series           = MI_ALT_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:  # mi-standard-issue-2013-pure-michigan
            series           = MI_STD_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95

    # ── Veteran subfolder ───────────────────────────────────────────────
    elif subfolder == 'mi-veteran':
        series           = MI_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    # ── Non-passenger subfolder ────────────────────────────────────────────
    elif subfolder == 'mi-non-passenger':
        series        = MI_NP_SERIES
        vehicle_class = 'Other'
        cat_id, cat_conf = CAT['Other / Specialty'], 80

    # ── Direct subfolder → category mappings ─────────────────────────────────
    elif subfolder == 'mi-first-responder':
        series           = MI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'mi-fraternal':
        series           = MI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'mi-outdoors':
        series           = MI_SPECIALTY_SERIES
        if 'agricultural' in core:
            cat_id, cat_conf = CAT['Agricultural'], 90
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'mi-schools':
        series           = MI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'mi-sports':
        series           = MI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # mi-specialty and unexpected
        series = MI_SPECIALTY_SERIES
        if any(kw in core for kw in ('cancer', 'sickle-cell', 'donate-life',
                                      'children-trust')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif core == 'patriotic':
            cat_id, cat_conf = CAT['Military / Veteran'], 88
        elif 'michigan-4h' in core:
            cat_id, cat_conf = CAT['Agricultural'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    MI_NAME_OVERRIDES = {
        # Standard-issue
        'mi-standard-issue-2013-pure-michigan':  'Standard Issue 2013 Pure Michigan',
        'mi-disability-plate':                   'Disability',
        'mi-mackinac-bridge-v2':                 'Mackinac Bridge V2',
        'mi-legacy-bicentennial-reissue':        'Legacy Bicentennial Reissue',
        'mi-legacy-black-reissue':               'Legacy Black Reissue',
        'mi-legacy-blue-reissue':                'Legacy Blue Reissue',
        'mi-water-winter-wonderland':            'Water Winter Wonderland',
        'mi-water-wonderland':                   'Water Wonderland',
        # Non-passenger
        'mi-fleet-rental':                       'Fleet Rental',
        'mi-permanent-trailer':                  'Permanent Trailer',
        # Veteran
        'mi-combat-wounded-veteran-purple-heart': 'Combat Wounded Veteran / Purple Heart',
        'mi-world-war-ii-veteran':               'World War II Veteran',
        'mi-persian-gulf-desert-storm-veteran':  'Persian Gulf / Desert Storm Veteran',
        # Specialty
        'mi-children-trust-michigan':            "Children's Trust Michigan",
        'mi-donate-life-plate':                  'Donate Life',
        'mi-michigan-4h-clubs':                  'Michigan 4-H Clubs',
        'mi-michigan-professional-fire-fighters-union':
                                                 'Michigan Professional Fire Fighters Union',
        "mi-michigan-state-firemen-s-association": "Michigan State Firemen's Association",
        'mi-police-officers-association-of-michigan':
                                                 'Police Officers Association of Michigan',
        'mi-grand-lodge-of-free-and-accepted-masons-of-michigan':
                                                 'Grand Lodge of Free and Accepted Masons of Michigan',
        'mi-michigan-fraternal-order-of-police':  'Michigan Fraternal Order of Police',
    }
    override_key = f'mi-{core_raw.lower()}'
    if override_key in MI_NAME_OVERRIDES:
        name_text = MI_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MI - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MN parser ─────────────────────────────────────────────────────────────────
def parse_mn(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MN (Minnesota) plate image across 8 subfolders.

    Series routing:
      mn-standard-issue (1987 plates)           → MN_STD_SERIES (732)
      mn-standard-issue (all other)             → MN_WHITE_SERIES (733)
      mn-non-passenger                          → MN_WHITE_SERIES (733)
      mn-veteran                                → MN_VETERAN_SERIES (735)
      mn-first-responder / mn-outdoors /
        mn-schools / mn-sports / mn-specialty   → MN_SPECIALTY_SERIES (734)

    Skip rules:
      mn-veteran-american-legion.png  (smaller dup — mn-american-legion.png kept)
      mn-veteran-vfw.png              (smaller dup — mn-vfw.png kept)
    """
    # ── Skip smaller duplicates ───────────────────────────────────────────────
    if actual_filename in ('mn-veteran-american-legion.png', 'mn-veteran-vfw.png'):
        return None

    # ── Normalise stem: strip Windows " (2)" suffix ──────────────────────────
    stem_clean = re.sub(r'\s*\(\d+\)\s*$', '', stem).strip()

    # Strip state prefix and any embedded extension
    core_raw = re.sub(r'^mn-', '', stem_clean, flags=re.IGNORECASE)
    core_raw = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', core_raw, flags=re.IGNORECASE)

    # ── Vehicle-class detection (longest suffix first) ────────────────────────
    vehicle_class = 'Passenger'
    moto_suffix   = ''
    if core_raw.endswith('-motorcycle-vertical'):
        vehicle_class = 'Motorcycle'
        core_raw      = core_raw[:-len('-motorcycle-vertical')]
        moto_suffix   = ' - Motorcycle Vertical'
    elif core_raw.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        core_raw      = core_raw[:-len('-motorcycle')]
        moto_suffix   = ' - Motorcycle'
    elif core_raw.endswith('-moped'):
        vehicle_class = 'Motorcycle'
        core_raw      = core_raw[:-len('-moped')]
        moto_suffix   = ' - Moped'

    # ── Series & category routing ─────────────────────────────────────────────
    cat_id, cat_conf = CAT['Other / Specialty'], 75  # safe default

    if subfolder == 'mn-standard-issue':
        if '1987' in core_raw:
            series = MN_STD_SERIES
            if 'disabled' in core_raw:
                cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
            else:
                cat_id, cat_conf = CAT['Standard Issue'], 95
        elif core_raw in ('classic', 'classic-car', 'collector', 'pioneer', 'street-rod'):
            series = MN_WHITE_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        elif core_raw in ('amateur-radio', 'citizen-band'):
            series = MN_WHITE_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disabled' in core_raw:
            series = MN_WHITE_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        else:
            series = MN_WHITE_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    elif subfolder == 'mn-non-passenger':
        series = MN_WHITE_SERIES
        if core_raw in ('state-vehicle', 'state-trailer', 'tax-exempt',
                        'tax-exempt-trailer', 'honorary-consulate', 'impound-plate'):
            cat_id, cat_conf = CAT['Government / Exempt'], 92
        elif core_raw == 'school-bus':
            cat_id, cat_conf = CAT['School'], 95
        elif 'farm' in core_raw:
            cat_id, cat_conf = CAT['Agricultural'], 90
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 78
        _np_cls = {
            'bus': 'Bus', 'school-bus': 'Bus', 'transit-bus': 'Bus',
            'farm-trailer': 'Trailer', 'recreational-trailer': 'Trailer',
            'semi-trailer': 'Trailer', 'state-trailer': 'Trailer',
            'trailer': 'Trailer', 'tax-exempt-trailer': 'Trailer',
            'farm-truck': 'Truck', 'truck-tractor': 'Truck',
        }
        vehicle_class = _np_cls.get(core_raw, 'Passenger')

    elif subfolder == 'mn-veteran':
        series = MN_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'mn-first-responder':
        series = MN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 92

    elif subfolder == 'mn-outdoors':
        series = MN_SPECIALTY_SERIES
        if 'agricultural' in core_raw:
            cat_id, cat_conf = CAT['Agricultural'], 90
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'mn-schools':
        series = MN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'mn-sports':
        series = MN_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # mn-specialty and unexpected
        series = MN_SPECIALTY_SERIES
        if 'support-our-troops' in core_raw:
            cat_id, cat_conf = CAT['Military / Veteran'], 88
        elif 'law-enforcement-memorial' in core_raw:
            cat_id, cat_conf = CAT['First Responder'], 88
        elif core_raw in ('missing-murdered-indigenous-relatives',
                          'remembering-victims-of-impaired-drivers'):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif core_raw in ('lions-club', 'rotary-international'):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    # ── Name overrides ────────────────────────────────────────────────────────
    MN_NAME_OVERRIDES = {
        # Standard-issue
        'mn-citizen-band':                                  'Citizen Band Radio',
        # Non-passenger
        'mn-non-commrercial-yga':                           'Non-Commercial YGA',
        'mn-commercial-yaa':                                'Commercial YAA',
        'mn-concrete-pumper-street-sweeper-fleet':          'Concrete Pumper / Street Sweeper Fleet',
        # Veteran
        'mn-minnesota-national-guardv1':                    'Minnesota National Guard V1',
        'mn-minnesota-national-guardv2':                    'Minnesota National Guard V2',
        'mn-veteran-world-war-ii':                          'Veteran World War II',
        'mn-veteran-world-war-ii-ribbon':                   'Veteran World War II Ribbon',
        'mn-veteran-combat-wounded-purple-heart':           'Veteran Combat Wounded / Purple Heart',
        'mn-veteran-ex-pow':                                'Veteran Ex-POW',
        'mn-veteran-laos-war-allied-vet':                   'Veteran Laos War Allied Veteran',
        'mn-vfw':                                           'Veterans of Foreign Wars',
        # Outdoors
        'mn-agricultural-plate':                            'Agricultural',
        # Specialty
        'mn-missing-murdered-indigenous-relatives':         'Missing and Murdered Indigenous Relatives',
        # Schools — abbreviations, apostrophes, and missing qualifiers
        'mn-collegiate-u-of-m':                             'Collegiate University of Minnesota',
        'mn-collegiate-u-of-m-crookston':                   'Collegiate University of Minnesota Crookston',
        'mn-collegiate-u-of-m-duluth':                      'Collegiate University of Minnesota Duluth',
        'mn-collegiate-u-of-m-morris':                      'Collegiate University of Minnesota Morris',
        'mn-collegiate-st-johns-v1':                        "Collegiate St. John's V1",
        'mn-collegiate-st-johns-v2':                        "Collegiate St. John's V2",
        'mn-collegiate-st-cloud-state':                     'Collegiate St. Cloud State University',
        'mn-collegiate-st-marys':                           "Collegiate St. Mary's University",
        'mn-collegiate-st-catherines-university':           "Collegiate St. Catherine's University",
        'mn-collegiate-st-olaf':                            'Collegiate St. Olaf College',
        'mn-collegiate-college-of-st-scholatica':           'Collegiate College of St. Scholastica',
        'mn-collegiate-college-of-st-benedict-v1':          'Collegiate College of St. Benedict V1',
        'mn-collegiate-college-of-st-benedict-v2':          'Collegiate College of St. Benedict V2',
        'mn-collegiate-gustavus-adolphus':                  'Collegiate Gustavus Adolphus College',
        'mn-collegiate-concordia-university-st-paul':       'Collegiate Concordia University St. Paul',
        'mn-collegiate-university-of-st-thomas':            'Collegiate University of St. Thomas',
        'mn-collegiate-university-of-northwestern-st-paul': 'Collegiate University of Northwestern St. Paul',
        'mn-collegiate-winona-state':                       'Collegiate Winona State University',
        # Sports
        'mn-minnesota-united-fc':                           'Minnesota United FC',
    }

    override_key = f'mn-{core_raw.lower()}'
    if override_key in MN_NAME_OVERRIDES:
        name_text = MN_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MN - {name_text}{moto_suffix}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MO parser ─────────────────────────────────────────────────────────────────
def parse_mo(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MO (Missouri) plate image across 10 subfolders.

    Series routing:
      mo-standard-issue:
        standard-issue-2018     → MO_STD_2018_SERIES (736), Standard Issue
        standard-issue-2008-bluebird → MO_STD_2008_SERIES (739), Standard Issue
        standard-issue-1997-show-me  → MO_STD_1997_SERIES (740), Standard Issue
        amateur-radio           → MO_STD_2018_SERIES (736), Radio/Amateur Radio
        historic/street-rod/custom-vehicle → MO_STD_2018_SERIES (736), Historical
      mo-non-passenger:
        former-missouri-legislator → MO_STD_2018_SERIES (736), Government/Exempt
        all others              → MO_CIVIC_SERIES (741)
      mo-veteran                → MO_VETERAN_SERIES (737)
      mo-first-responder / mo-fraternal / mo-outdoors /
        mo-schools / mo-sports / mo-specialty → MO_SPECIALTY_SERIES (738)
    """
    core_raw = re.sub(r'^mo-', '', stem, flags=re.IGNORECASE)
    core_raw = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', core_raw, flags=re.IGNORECASE)

    vehicle_class = 'Passenger'
    cat_id, cat_conf = CAT['Other / Specialty'], 75

    if subfolder == 'mo-standard-issue':
        if core_raw == 'standard-issue-2018':
            series = MO_STD_2018_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif core_raw == 'standard-issue-2008-bluebird':
            series = MO_STD_2008_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif core_raw == 'standard-issue-1997-show-me':
            series = MO_STD_1997_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif core_raw == 'amateur-radio':
            series = MO_STD_2018_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        else:  # historic, street-rod, custom-vehicle
            series = MO_STD_2018_SERIES
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90

    elif subfolder == 'mo-non-passenger':
        if core_raw == 'former-missouri-legislator':
            series = MO_STD_2018_SERIES
            cat_id, cat_conf = CAT['Government / Exempt'], 88
        else:
            series = MO_CIVIC_SERIES
            if core_raw in ('clay-county-sheriff', 'liberty-police',
                            'coroners-office-mcmea'):
                cat_id, cat_conf = CAT['Government / Exempt'], 92
            elif core_raw == 'liberty-public-schools':
                cat_id, cat_conf = CAT['School'], 95
            elif core_raw in ('official-vehicle', 'kansas-city-mo',
                              'lee-summitt-airport', 'vanpool', 'fleet',
                              'shuttle-bus'):
                cat_id, cat_conf = CAT['Government / Exempt'], 88
            else:
                cat_id, cat_conf = CAT['Other / Specialty'], 78
        if core_raw == 'shuttle-bus':
            vehicle_class = 'Bus'

    elif subfolder == 'mo-veteran':
        series = MO_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'mo-first-responder':
        series = MO_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 92

    elif subfolder == 'mo-fraternal':
        series = MO_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 90

    elif subfolder == 'mo-outdoors':
        series = MO_SPECIALTY_SERIES
        if 'ducks-unlimited' in core_raw or 'bee-friendly' in core_raw:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90
        elif 'conservation' in core_raw or 'cave' in core_raw or \
                'great-rivers' in core_raw:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 88

    elif subfolder == 'mo-schools':
        series = MO_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'mo-sports':
        series = MO_SPECIALTY_SERIES
        if 'special-olympics' in core_raw:
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        else:
            cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # mo-specialty
        series = MO_SPECIALTY_SERIES
        if 'back-the-blue' in core_raw:
            cat_id, cat_conf = CAT['First Responder'], 85
        elif any(kw in core_raw for kw in ('fight-terrorism', 'god-bless-america',
                                            'dont-tread-on-me', 'we-shall-not-forget')):
            cat_id, cat_conf = CAT['Military / Veteran'], 85
        elif any(kw in core_raw for kw in ('heart-association', 'breast-cancer',
                                            'organ-donor', 'childrens-trust',
                                            'choose-life', 'hearing-impaired',
                                            'nurses-foundation')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core_raw for kw in ('eagle-scout', 'order-of-the-arrow',
                                            'tribe-mic-o-say')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 88
        elif any(kw in core_raw for kw in ('gateway-arch', 'route-66',
                                            'wilsons-creek', 'friends-of-arrow-rock')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(kw in core_raw for kw in ('zoo', 'botanical-garden')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 88
        elif any(kw in core_raw for kw in ('missouri-4-h', 'mo-ag-agribusiness')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    MO_NAME_OVERRIDES = {
        # Standard issue
        'mo-standard-issue-2018':   'Standard Issue 2018 Bicentennial',
        # Non-passenger
        'mo-lee-summitt-airport':   "Lee's Summit Airport",
        'mo-fleet':                 'Fleet',
        # Veteran
        'mo-former-p-o-w':          'Former POW',
        'mo-combat-infrantryman':   'Combat Infantryman',
        'mo-veterans-of-foreign-wars-vfw': 'Veterans of Foreign Wars (VFW)',
        'mo-wartime-disabled-dav':  'Wartime Disabled DAV',
        'mo-some-gave-all-gold-star': 'Some Gave All / Gold Star',
        'mo-missouri-remembers-pow-mia': 'Missouri Remembers POW-MIA',
        'mo-bronze-star-valor':     'Bronze Star with Valor',
        # Schools
        'mo-maryville-university-of-st-louis':
            'Maryville University of St. Louis',
        'mo-university-of-health-sciences-and-pharmacy-in-st-louis':
            'University of Health Sciences and Pharmacy in St. Louis',
        'mo-university-of-missouri-columbia-mizzou':
            'University of Missouri - Columbia (Mizzou)',
        'mo-southeast-missouri-state':
            'Southeast Missouri State University',
        'mo-arkansas-alumni-go-hogs':
            'University of Arkansas Alumni (Go Hogs)',
        # Specialty
        'mo-missouri-federation-of-square-amp-round-dance-clubs':
            'Missouri Federation of Square & Round Dance Clubs',
        'mo-tribe-mic-o-say-kansas-city-district':
            'Tribe Mic-O-Say Kansas City District',
        'mo-tribe-mic-o-say-st-joseph-district':
            'Tribe Mic-O-Say St. Joseph District',
        'mo-search-and-rescue-sarcom': 'Search and Rescue SARCOM',
        'mo-mo-ag-agribusiness':    'MO Ag Agribusiness',
        'mo-mkn-teamsters':         'MKN Teamsters',
    }

    override_key = f'mo-{core_raw.lower()}'
    if override_key in MO_NAME_OVERRIDES:
        name_text = MO_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MO - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MS parser ─────────────────────────────────────────────────────────────────
def parse_ms(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MS (Mississippi) plate image across 9 subfolders.

    Series routing:
      ms-standard-issue:
        2024 / magnolia in name           → MS_STD_2024_SERIES (743)
        blackout / standard-2022 in name  → MS_BLACKOUT_SERIES (744)
        all others (2019, antique, radio,
          historic, street-rod)           → MS_STD_2019_SERIES (742)
      ms-veteran-military                 → MS_VETERAN_SERIES  (745)
      ms-non-passenger and government     → MS_NONPASS_SERIES  (746)
      all other subfolders (first-responder, fraternal, outdoors,
        schools, sports, specialty)       → MS_SPECIALTY_SERIES (747)
    """
    core_raw = re.sub(r'^ms-', '', stem, flags=re.IGNORECASE)
    core_raw = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', core_raw, flags=re.IGNORECASE)
    core = core_raw.lower()

    vehicle_class = 'Passenger'
    cat_id, cat_conf = CAT['Other / Specialty'], 75

    # ── vehicle class ──────────────────────────────────────────────────────
    if 'motorcycle' in core:
        vehicle_class = 'Motorcycle'
    elif 'school-bus' in core or 'church-bus' in core:
        vehicle_class = 'Bus'

    # ── series + category by subfolder ────────────────────────────────────
    if subfolder == 'ms-standard-issue':
        if any(x in core for x in ('2024', 'magnolia')):
            series = MS_STD_2024_SERIES
            if 'disabled' in core:
                cat_id, cat_conf = CAT['Disabled / Accessibility'], 92
            else:
                cat_id, cat_conf = CAT['Standard Issue'], 95
        elif any(x in core for x in ('blackout', 'standard-2022')):
            series = MS_BLACKOUT_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        else:  # 2019-gold, antique, amateur-radio, historical, street-rod
            series = MS_STD_2019_SERIES
            if 'amateur-radio' in core:
                cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
            elif any(x in core for x in ('antique', 'historical', 'street-rod')):
                cat_id, cat_conf = CAT['Historical / Commemorative'], 90
            else:
                cat_id, cat_conf = CAT['Standard Issue'], 95

    elif subfolder == 'ms-veteran-military':
        series = MS_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'ms-non-passenger and government':
        series = MS_NONPASS_SERIES
        if any(x in core for x in ('dealer', 'manufacturer', 'wholesaler')):
            cat_id, cat_conf = CAT['Dealer / Manufacturer'], 92
        elif any(x in core for x in ('farm', 'harvest')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        else:
            cat_id, cat_conf = CAT['Government / Exempt'], 88

    elif subfolder == 'ms-first-responder':
        series = MS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 92

    elif subfolder == 'ms-fraternal':
        series = MS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 90

    elif subfolder == 'ms-outdoors':
        series = MS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'ms-schools':
        series = MS_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'ms-sports':
        series = MS_SPECIALTY_SERIES
        if 'nascar' in core:
            cat_id, cat_conf = CAT['Sports Team'], 92
        elif 'bicycle' in core:
            cat_id, cat_conf = CAT['Conservation / Environment'], 80
        elif 'athletic' in core or 'gulfport-police' in core:
            cat_id, cat_conf = CAT['First Responder'], 78
        else:
            cat_id, cat_conf = CAT['Sports Team'], 88

    else:  # ms-specialty
        series = MS_SPECIALTY_SERIES
        if any(x in core for x in ('alzheimers', 'autism', 'breast-cancer',
                                    'cancer', 'diabetic', 'down-syndrome',
                                    'dyslexia', 'hearing-impaired', 'organ-donor',
                                    'blood-services', 'nurses', 'st-jude',
                                    'le-bonheur', 'childrens-hospital',
                                    'friends-of-childrens', 'catch-a-dream',
                                    'childrens-advocacy', 'toughest-kids',
                                    'fannie-lou-hamer', 'protect-life',
                                    'choose-life', 'family-physicians',
                                    'profession-of-pharmacy', 'dental-hygienist',
                                    'juvenile-diabetes')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(x in core for x in ('cattlemans', 'sweet-potatoes',
                                      'farm-families', 'loggers', 'equine',
                                      'pearl-river-valley-water',
                                      'electric-power')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif any(x in core for x in ('aquarium', 'jackson-zoo',
                                      'friends-of-jackson-county-animal')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 85
        elif any(x in core for x in ('home-of-the-blues', 'elvis',
                                      'public-broadcasting', 'childrens-museum')):
            cat_id, cat_conf = CAT['Arts / Culture'], 88
        elif any(x in core for x in ('historic-natchez', 'state-flag',
                                      'gulf-coast-regional-tourism')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif any(x in core for x in ('4h-club', 'boy-scouts', 'civil-air-patrol',
                                      'band-of-choctaw', 'national-rifle',
                                      'volunteer-service', 'after-school',
                                      'support-teachers', 'motosteps',
                                      'sunflower-county-ministerial',
                                      'god-bless-america', 'i-love-mississippi')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 80
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    MS_NAME_OVERRIDES = {
        # Standard issue
        'ms-standard-issue-2019-gold':                  'Standard Issue 2019 Gold Seal',
        'ms-standard-issue-2024-magnolia':              'Standard Issue 2024 Magnolia',
        'ms-standard-issue-2024-magnolia-personalized': 'Standard Issue 2024 Magnolia Personalized',
        'ms-2019-gold-motorcycle':                      '2019 Gold Seal Motorcycle',
        'ms-standard-2022-standard-passenger-black':   '2022 Blackout Standard Passenger',
        'ms-blackout-passenger':                        '2022 Blackout Passenger',
        'ms-blackout-pickup':                           '2022 Blackout Pickup',
        'ms-blackout-motorcycle':                       '2022 Blackout Motorcycle',
        # Non-passenger
        'ms-2019-gold-series':                          'Non-Passenger 2019 Gold Seal',
        'ms-blackout-b10':                              '2022 Blackout B-10',
        'ms-blackout-f-10':                             '2022 Blackout F-10',
        'ms-b16-b80':                                   'B16-B80 Non-Passenger',
        'ms-f16-f80':                                   'F16-F80 Non-Passenger',
        'ms-farm-f16':                                  'Farm F-16',
        # Veteran
        'ms-veteran-disabled american veteran':         'Disabled American Veteran',
        'ms-disabled-american-veteran-less-than-100':   'Disabled American Veteran - Under 100%',
        'ms-ex-prisoner-of-war':                        'Ex-Prisoner of War',
        # Specialty / abbreviation fixes
        'ms-4h-club':                                   '4-H Club',
        'ms-ev-mississippi':                            'EV Mississippi',
        'ms-mw-stringer-grand-lodge-f-am-prince-hall-affiliated':
            'M.W. Stringer Grand Lodge F.&A.M. Prince Hall Affiliated',
        'ms-ms-law-enforcement-officer-association-supporter':
            'MS Law Enforcement Officer Association Supporter',
        'ms-i-love-mississippi-sunflower-consolidated-school-preservatio':
            'I Love Mississippi Sunflower Consolidated School Preservation',
        'ms-juvenile-diabetes-research-foundation-v1':
            'Juvenile Diabetes Research Foundation - v1',
        'ms-juvenile-diabetes-research-foundation-v2':
            'Juvenile Diabetes Research Foundation - v2',
        # NASCAR — fix capitalisation and add driver numbers
        'ms-nascar-01-ross-chastain':       'NASCAR #01 Ross Chastain',
        'ms-nascar-03-dale-earnhardt':      'NASCAR #03 Dale Earnhardt',
        'ms-nascar-04-kevin-harvick':       'NASCAR #04 Kevin Harvick',
        'ms-nascar-08-kyle-bush':           'NASCAR #08 Kyle Bush',
        'ms-nascar-11-denny-hamlin':        'NASCAR #11 Denny Hamlin',
        'ms-nascar-19-martin-truex-jr':     'NASCAR #19 Martin Truex Jr.',
        'ms-nascar-43-richard-petty':       'NASCAR #43 Richard Petty',
        'ms-nascar-47-ricky-stenhouse-jr':  'NASCAR #47 Ricky Stenhouse Jr.',
        'ms-nascar-54-ty-gibbs':            'NASCAR #54 Ty Gibbs',
        'ms-nascar-ford-racing':            'NASCAR Ford Racing',
        'ms-nascar-generic-driver':         'NASCAR Generic Driver',
        'ms-nascar-hall-of-fame':           'NASCAR Hall of Fame',
        'ms-nascar-racing':                 'NASCAR Racing',
        'ms-nascar-stripe':                 'NASCAR Stripe',
        'ms-nascar-track-scene':            'NASCAR Track Scene',
    }

    override_key = f'ms-{core}'
    if override_key in MS_NAME_OVERRIDES:
        name_text = MS_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MS - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── MT parser ─────────────────────────────────────────────────────────────────
def parse_mt(stem: str, subfolder: str, actual_filename: str):
    """Parse a single MT (Montana) plate image across 8 subfolders.

    Series routing:
      mt-standard-issue:
        2006 / gold-font          → MT_STD_2006_SERIES (750)
        2000                      → MT_STD_2000_SERIES (751)
        1991 / white-font         → MT_STD_1991_SERIES (752)
        1989 / centennial         → MT_STD_1989_SERIES (753)
        all others (2010, radio,
          physical-disability,
          vintage)                → MT_STD_2010_SERIES (749)
      mt-military                 → MT_VETERAN_SERIES  (748)
      all other subfolders        → MT_SPECIALTY_SERIES (754)
    """
    core_raw = re.sub(r'^mt-', '', stem, flags=re.IGNORECASE)
    core_raw = re.sub(r'\.(jpg|jpeg|png|gif|webp)$', '', core_raw, flags=re.IGNORECASE)
    core = core_raw.lower()

    vehicle_class = 'Passenger'
    cat_id, cat_conf = CAT['Other / Specialty'], 75

    if 'motorcycle' in core:
        vehicle_class = 'Motorcycle'

    # ── series + category ──────────────────────────────────────────────────
    if subfolder == 'mt-standard-issue':
        if '2006' in core or 'gold-font' in core:
            series = MT_STD_2006_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif '2000' in core:
            series = MT_STD_2000_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif '1991' in core or 'white-font' in core:
            series = MT_STD_1991_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif '1989' in core or 'centennial' in core:
            series = MT_STD_1989_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'amateur-radio' in core:
            series = MT_STD_2010_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'physical-disability' in core:
            series = MT_STD_2010_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 92
        else:  # 2010-blue, vintage, anything else
            series = MT_STD_2010_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif subfolder == 'mt-military':
        series = MT_VETERAN_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'mt-first-responders':
        series = MT_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 92

    elif subfolder == 'mt-fraternal':
        series = MT_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 90

    elif subfolder == 'mt-outdoors':
        series = MT_SPECIALTY_SERIES
        if any(x in core for x in ('stockgrowers', 'cutting-horse', 'farm-bureau',
                                    'grains', 'livestock', 'chicks-n-chaps',
                                    'agricultural-heritage', 'horse-sanctuary',
                                    'heart-for-horses', 'a-heart',
                                    'missoula-horse-council', 'les-haven',
                                    'windhorse', 'beartooth-back-country-horsemen',
                                    'united-in-light')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'mt-schools':
        series = MT_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'mt-sports':
        series = MT_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # mt-specialty
        series = MT_SPECIALTY_SERIES
        if any(x in core for x in ('symphony', 'choral-festival', 'carousel',
                                    'pbs', 'public-radio', 'cowboy-hall',
                                    'mobile-museum', 'custer-battlefield',
                                    'elizabeth-custer', 'downtown-foundation',
                                    'main-street', 'lewis-clark-bicentennial',
                                    'international-choral')):
            cat_id, cat_conf = CAT['Arts / Culture'], 88
        elif any(x in core for x in ('farm-bureau', 'grains', 'stockgrowers',
                                      'cutting-horse', 'better-the-farm',
                                      'food-ag-coalition', 'future-farmers',
                                      'livestock-loss', 'chicks-n-chaps',
                                      'agricultural-heritage', '4-h',
                                      'montana-grains')):
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif any(x in core for x in ('cancer', 'organ-eye', 'tough-enough',
                                      'mental-health', 'medical-foundation',
                                      'postpartum', 'violence-free',
                                      'developmental-educational',
                                      'bridgercare', 'heart-of-the-valley',
                                      'love-for-lexie', 'mercy-flight',
                                      'options-clinic', 'spay-neuter')):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(x in core for x in ('blackfeet-tribe', 'fort-belknap-indian',
                                      'chippewa-cree', 'northern-cheyenne',
                                      'blackfoot-challenge', 'shriners')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        elif any(x in core for x in ('move-over', 'motorcycle-safety',
                                      'safety-service', 'patrol-base')):
            cat_id, cat_conf = CAT['First Responder'], 82
        elif any(x in core for x in ('1776-foundation', 'dont-tread',
                                      'first-amendment')):
            cat_id, cat_conf = CAT['Military / Veteran'], 80
        elif any(x in core for x in ('school', 'beyond-the-classroom',
                                      'home-and-private', 'billings-christian')):
            cat_id, cat_conf = CAT['School'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 75

    MT_NAME_OVERRIDES = {
        # Standard issue
        'mt-standard-issue-2010-blue':                  'Standard Issue 2010 Blue',
        'mt-standard-issue-2006-gold-font':             'Standard Issue 2006 Gold Font',
        'mt-standard-issue-2000-blue-font':             'Standard Issue 2000 Blue Font',
        'mt-standard-issue-1991-white-font':            'Standard Issue 1991 White Font',
        'mt-standard-issue-1989-centennial':            'Standard Issue 1989 Centennial',
        'mt-2010-standard-issue-amateur-radio-operator': 'Amateur Radio Operator',
        'mt-2010-standard-issue-physical-disability':   'Physical Disability',
        # Military typo fix
        'mt-miliary-disabled-veteran':                  'Military Disabled Veteran',
        # Military proper nouns
        'mt-uss-montana-ssn-794':                       'USS Montana SSN-794',
        # Specialty abbreviation / punctuation fixes
        'mt-dont-tread-on-mt':                          "Don't Tread on MT",
        'mt-montana-4-h-foundation':                    'Montana 4-H Foundation',
        'mt-alternative-energy-resources-organization-aero':
            'Alternative Energy Resources Organization (AERO)',
        'mt-experimental-aircraft-association-eaa-chapter-517':
            'Experimental Aircraft Association (EAA) Chapter 517',
        'mt-montana-sheriffs-and-peace-officers-assoc-2025':
            'Montana Sheriffs and Peace Officers Association 2025',
        'mt-montana-stockgrowers-assn':                 'Montana Stockgrowers Association',
        'mt-montana-cutting-horse-assn':                'Montana Cutting Horse Association',
        'mt-ecology-project-intl':                      'Ecology Project International',
        'mt-university-of-montana-grizzly-scholarship-assn-v1':
            'University of Montana Grizzly Scholarship Association - v1',
        'mt-university-of-montana-grizzly-scholarship-assn-v2':
            'University of Montana Grizzly Scholarship Association - v2',
        'mt-youth-overcoming-lifes-obstacles-v1':       "Youth Overcoming Life's Obstacles - v1",
        'mt-youth-overcoming-lifes-obstacles-v2':       "Youth Overcoming Life's Obstacles - v2",
        # v1 / v2 variants
        'mt-montana-natural-history-center-v1':         'Montana Natural History Center - v1',
        'mt-montana-natural-history-center-v2':         'Montana Natural History Center - v2',
        'mt-montana-wildlife-federation-v1':            'Montana Wildlife Federation - v1',
        'mt-montana-wildlife-federation-v2':            'Montana Wildlife Federation - v2',
        'mt-montana-wild-sheep-foundation-v1':          'Montana Wild Sheep Foundation - v1',
        'mt-montana-wild-sheep-foundation-v2':          'Montana Wild Sheep Foundation - v2',
        'mt-prickly-pear-land-trust-v1':                'Prickly Pear Land Trust - v1',
        'mt-prickly-pear-land-trust-v2':                'Prickly Pear Land Trust - v2',
        'mt-compassion-montana-v1':                     'Compassion Montana - v1',
        'mt-compassion-montana-v2':                     'Compassion Montana - v2',
        'mt-salish-kootenai-college-v1':                'Salish Kootenai College - v1',
        'mt-salish-kootenai-college-v2':                'Salish Kootenai College - v2',
        'mt-university-of-providence-v1':               'University of Providence - v1',
        'mt-university-of-providence-v2':               'University of Providence - v2',
        'mt-montana-state-golf-association-v1':         'Montana State Golf Association - v1',
        # Mixed-case filenames (Montana- prefix instead of mt-)
        'mt-montana-council-of-trout-unlimited-2023':   'Montana Council of Trout Unlimited 2023',
        'mt-montana-family-institute-2023':             'Montana Family Institute 2023',
        'mt-montana-hope-project-2023-1':               'Montana Hope Project 2023',
    }

    # Handle Montana- prefix filenames (e.g. Montana-Council-of-Trout-Unlimited-2023.jpg)
    if stem.startswith('Montana-') or stem.startswith('montana-'):
        raw_no_prefix = re.sub(r'^[Mm]ontana-', '', stem)
        override_key = f'mt-montana-{raw_no_prefix.lower()}'
    else:
        override_key = f'mt-{core}'

    if override_key in MT_NAME_OVERRIDES:
        name_text = MT_NAME_OVERRIDES[override_key]
    else:
        name_text = to_title(core_raw)
    plate_name = f'MT - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── NC parser ─────────────────────────────────────────────────────────────────
def parse_nc(stem: str, subfolder: str, actual_filename: str):
    """Parse a single NC (North Carolina) plate image across 9 subfolders.

    Series routing:
      nc-standard-issue           → NC_STD_SERIES (756), Standard Issue
      nc-non-passenger-government → NC_NON_PASS_SERIES (757), Government/Exempt, vehicle Other
      all other subfolders        → NC_SPECIALTY_SERIES (758)

    Category routing:
      nc-standard-issue           → Standard Issue (95%)
      nc-non-passenger-government → Government / Exempt (95%), vehicle Other
      nc-military-veteran         → Military / Veteran (95%)
      nc-first-responder          → First Responder (95%)
      nc-fraternal                → Fraternal / Civic (90%)
      nc-outdoors                 → Conservation / Environment (95%)
      nc-schools                  → School (95%)
      nc-sports                   → Sports Team (90%)
      nc-specialty                → keyword-based (Health, Historical, Arts, Conservation, default Other)
    """
    if not stem.lower().startswith('nc-'):
        return None

    core_raw = stem[3:]   # strip 'nc-' prefix, preserve original case
    core     = core_raw.lower()

    # ── Full-stem overrides (before motorcycle detection) ─────────────────────
    # Used when the motorcycle suffix is part of the plate type name, not a descriptor.
    FULL_STEM = {
        'nc-antique-motorcycle': ('NC - Antique Motorcycle', 'Motorcycle'),
        'nc-motorcycle':         ('NC - Motorcycle',         'Motorcycle'),
    }
    if stem.lower() in FULL_STEM:
        plate_name, vehicle_class = FULL_STEM[stem.lower()]
        moto_suffix = ''
    else:
        # ── Motorcycle detection ──────────────────────────────────────────────
        if core.endswith('-motorcycle'):
            vehicle_class = 'Motorcycle'
            core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
            core     = core_raw.lower()
            moto_suffix = ' - Motorcycle'
        else:
            vehicle_class = 'Passenger'
            moto_suffix   = ''

        # ── Name overrides ────────────────────────────────────────────────────
        NAME_OVERRIDES = {
            'pow-mia':                              'POW MIA',
            'als':                                  'ALS',
            'a-t-university':                       'A&T University',
            'world-war-ll-veteran':                 'World War II Veteran',
            # US — no periods per naming convention
            'us-air-force-academy':                 'US Air Force Academy',
            'us-air-force-veteran':                 'US Air Force Veteran',
            'us-army-veteran':                      'US Army Veteran',
            'us-coast-guard-academy':               'US Coast Guard Academy',
            'us-coast-guard-veteran':               'US Coast Guard Veteran',
            'us-merchant-marine-academy':           'US Merchant Marine Academy',
            'us-military-academy':                  'US Military Academy',
            'us-naval-academy':                     'US Naval Academy',
            'us-navy-submarine-veteran':            'US Navy Submarine Veteran',
            'us-navy-veteran':                      'US Navy Veteran',
            # NASCAR
            'nascar-ford-racing':                   'NASCAR Ford Racing',
            'nascar-generic-design':                'NASCAR Generic Design',
            'nascar-hall-of-fame':                  'NASCAR - Hall of Fame',
            'nascar-race-fan':                      'NASCAR Race Fan',
            # Multi-part names — dash separates qualifier segments
            'dale-earnhardt-hall-of-fame':          'Dale Earnhardt - Hall of Fame',
            'standard-issue-2009-first-in-flight':  'Standard Issue - 2009 - First In Flight',
            # Other overrides
            'homes4nc':                             'Homes4NC',
            'arts-nc':                              'Arts NC',
            'the-v-foundation':                     'The V Foundation',
            'ronald-mcdonald-house':                'Ronald McDonald House',
        }
        name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
        plate_name = f'NC - {name_text}{moto_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'nc-standard-issue':
        series           = NC_STD_SERIES
        cat_id, cat_conf = CAT['Standard Issue'], 95
        # Vehicle class refinement for specific standard-issue types
        if 'moped' in core:
            vehicle_class = 'Other'
        elif 'antique' in core and vehicle_class != 'Motorcycle':
            vehicle_class = 'Other'

    elif subfolder == 'nc-non-passenger-government':
        series           = NC_NON_PASS_SERIES
        cat_id, cat_conf = CAT['Government / Exempt'], 95
        vehicle_class    = 'Other'

    elif subfolder == 'nc-military-veteran':
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'nc-first-responder':
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'nc-fraternal':
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 90

    elif subfolder == 'nc-outdoors':
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 95

    elif subfolder == 'nc-schools':
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'nc-sports':
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # nc-specialty and catch-all
        series           = NC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72
        # Keyword-based refinement for nc-specialty
        if any(kw in core for kw in ('cancer', 'autism', 'diabetes', 'hospice',
                                     'nurse', 'sclerosis', 'v-foundation',
                                     'donate-life', 'ronald-mcdonald', 'kids-first')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif any(kw in core for kw in ('als',)):
            cat_id, cat_conf = CAT['Health & Awareness'], 95
        elif any(kw in core for kw in ('battle', 'guilford', 'heritage',
                                       'native-american', 'cherokee', 'piedmont-airlines')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif any(kw in core for kw in ('aquarium', 'museum', 'maritime', 'shag',
                                       'dance', 'zoological', 'aurora-fossil', 'arts')):
            cat_id, cat_conf = CAT['Arts / Culture'], 85
        elif any(kw in core for kw in ('litter', 'venus-flytrap', 'animal')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 80

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     34,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── NH parser ─────────────────────────────────────────────────────────────────
def parse_nh(stem: str, subfolder: str, actual_filename: str):
    """Parse a single NH (New Hampshire) plate image across 4 subfolders.

    Series routing:
      nh-standard-issue  → NH_STD_1999_SERIES (771) for most variants
                         → NH_STD_2026_SERIES (772) for the 2026 Bicentennial design
      nh-non-passenger   → NH_NON_PASS_SERIES (773), Government / Exempt, Other class
                           exception: nh-ambulance → First Responder, Other
      nh-conservation    → NH_SPECIALTY_SERIES (774), Conservation / Environment
      nh-military-veteran→ NH_SPECIALTY_SERIES (774), Military / Veteran

    Vehicle class notes:
      antique, moped, handicap variants → Other
      motorcycle variants               → Motorcycle
      all others                        → Passenger

    Note: nh-standard-issue-2026-sesquicentennial.avif filename differs from the
    Filament series name; override maps it to 'Standard Issue - 2026 - Bicentennial'.
    """
    if not stem.lower().startswith('nh-'):
        return None

    core_raw = stem[3:]   # strip 'nh-' prefix
    core     = core_raw.lower()

    # ── Full-stem overrides ───────────────────────────────────────────────────
    # Used when: (a) vehicle_class needs to be non-Passenger without motorcycle
    # detection, or (b) the name requires explicit v1/v2 labeling.
    FULL_STEM = {
        'nh-antique':             ('NH - Antique - v1',       'Other'),
        'nh-antique-v2':          ('NH - Antique - v2',       'Other'),
        'nh-antique-motorcycle':  ('NH - Antique Motorcycle',  'Motorcycle'),
        'nh-motorcycle':          ('NH - Motorcycle',          'Motorcycle'),
        'nh-moped':               ('NH - Moped',               'Other'),
        'nh-handicap':            ('NH - Handicap',            'Other'),
    }
    if stem.lower() in FULL_STEM:
        plate_name, vehicle_class = FULL_STEM[stem.lower()]
        moto_suffix = ''
    else:
        # ── Motorcycle detection ──────────────────────────────────────────────
        if core.endswith('-motorcycle'):
            vehicle_class = 'Motorcycle'
            core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
            core     = core_raw.lower()
            moto_suffix = ' - Motorcycle'
        else:
            vehicle_class = 'Passenger'
            moto_suffix   = ''

        # ── Name overrides ────────────────────────────────────────────────────
        NAME_OVERRIDES = {
            # Standard issue — multi-part qualifiers; filename typo corrected
            'standard-issue-1999-live-free-or-die':     'Standard Issue - 1999 - Live Free or Die',
            'standard-issue-2026-sesquicentennial':     'Standard Issue - 2026 - Bicentennial',
        }
        name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
        plate_name = f'NH - {name_text}{moto_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'nh-standard-issue':
        cat_id, cat_conf = CAT['Standard Issue'], 95
        if '2026' in core or 'sesquicentennial' in core:
            series = NH_STD_2026_SERIES
        else:
            series = NH_STD_1999_SERIES

    elif subfolder == 'nh-non-passenger':
        series        = NH_NON_PASS_SERIES
        vehicle_class = 'Other'
        if 'ambulance' in core:
            cat_id, cat_conf = CAT['First Responder'], 95
        else:
            cat_id, cat_conf = CAT['Government / Exempt'], 90

    elif subfolder == 'nh-conservation':
        series           = NH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 95

    elif subfolder == 'nh-military-veteran':
        series           = NH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    else:
        series           = NH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     30,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── NY parser ─────────────────────────────────────────────────────────────────
def parse_ny(stem: str, subfolder: str, actual_filename: str):
    """Parse a single NY (New York) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      ny-standard-issue  → year-routed: 1986→800, 2001→796, 2010→626, 2020→624
      ny-non-passenger   → suffix-routed: empire-gold→797, empire-state→798,
                           excelsior→799
      all others         → NY_SPECIALTY_SERIES (625)

    Vehicle class:
      -motorcycle or -motor-cycle suffix → Motorcycle (appended to name)
      -vehicle suffix                    → Passenger (suffix stripped from name)
      non-passenger commercial/tow/taxi  → Commercial
      non-passenger trailer              → Trailer
      all others                         → Passenger
    """
    if not stem.lower().startswith('ny-'):
        return None

    core_raw = stem[3:]        # strip 'ny-'
    core     = core_raw.lower()

    # ── Vehicle class / suffix detection ─────────────────────────────────────
    vehicle_class = 'Passenger'
    mc_suffix     = ''
    if core.endswith('-motorcycle') or core.endswith('-motor-cycle'):
        vehicle_class = 'Motorcycle'
        mc_suffix     = ' - Motorcycle'
        core_raw = re.sub(r'-[Mm]otor-?[Cc]ycle$', '', core_raw)
        core     = re.sub(r'-motor-?cycle$',         '', core)
    elif core.endswith('-vehicle'):
        core_raw = core_raw[:-8]
        core     = core[:-8]

    # ── v-suffix extraction ───────────────────────────────────────────────────
    v_suffix = ''
    v_match  = re.search(r'-(v\d+)$', core)
    if v_match:
        v_suffix  = f' - {v_match.group(1)}'
        core_raw  = core_raw[:v_match.start()]
        core      = core[:v_match.start()]

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue
        'standard-issue-1986-statue-liberty':                            'Standard Issue - 1986 - Statue of Liberty',
        'standard-issue-2001-empire-state':                              'Standard Issue - 2001 - Empire State',
        'standard-issue-2010-empire-gold':                               'Standard Issue - 2010 - Empire Gold',
        'standard-issue-2020-excelsior':                                 'Standard Issue - 2020 - Excelsior',
        # Non-passenger
        'commercial-empire-gold':                                        'Commercial - Empire Gold',
        'commercial-empire-state':                                       'Commercial - Empire State',
        'commercial-excelsior':                                          'Commercial - Excelsior',
        'dealer-empire-gold':                                            'Dealer - Empire Gold',
        'taxi-limousine-empire-gold':                                    'Taxi / Limousine - Empire Gold',
        'tow-truck-empire-gold':                                         'Tow Truck - Empire Gold',
        'trailer-empire-gold':                                           'Trailer - Empire Gold',
        'trailer-empire-state':                                          'Trailer - Empire State',
        'trailer-excelsior':                                             'Trailer - Excelsior',
        # First responder
        '9-11-remembrance':                                              '9/11 Remembrance',
        'assn-of-former-state-troopers':                                 'Association of Former State Troopers',
        'emergency-medical-technician-paramedic':                        'Emergency Medical Technician - Paramedic',
        'firefighters-assn-of-the-state-of-new-york':                   'Firefighters Association of the State of New York',
        'international-law-enforcement-officers-assn':                   'International Law Enforcement Officers Association',
        'new-york-honorary-fire-chiefs-assn':                            'New York Honorary Fire Chiefs Association',
        'new-york-state-police-investigators-association-surgeons-gro':  'New York State Police Investigators Association - Surgeons Group',
        'police-benevolent-assn':                                        'Police Benevolent Association',
        'police-surgeons-benevolent-assn':                               'Police Surgeons Benevolent Association',
        'uniformed-firefighters-of-new-york-retired':                    'Uniformed Firefighters of New York - Retired',
        # Fraternal
        'rotary-intl':                                                   'Rotary International',
        # Military
        '40-8-the-grande-voiture-du-new-york-la-societe-des-quarante-':  '40 and 8 - La Grande Voiture de New York',
        'amvets':                                                        'AMVETS',
        'submarine-veterans-silent-service':                             'Submarine Veterans - Silent Service',
        'us-air-force-veteran':                                          'US Air Force Veteran',
        'us-army-veteran':                                               'US Army Veteran',
        'us-coast-guard-veteran':                                        'US Coast Guard Veteran',
        'us-marine-corps-veteran':                                       'US Marine Corps Veteran',
        'us-naval-armed-guard':                                          'US Naval Armed Guard',
        'us-navy-veteran':                                               'US Navy Veteran',
        'us-veteran':                                                    'US Veteran',
        'world-war-ii-veterans':                                         'World War II Veterans',
        # Schools
        'st-lawrence-university':                                        'St. Lawrence University',
        'united-states-military-academy-west-point':                     'United States Military Academy - West Point',
        # Outdoors
        'fishing-striped-bass':                                          'Fishing - Striped Bass',
        'fishing-trout':                                                 'Fishing - Trout',
        'fishing-walleye':                                               'Fishing - Walleye',
        'hunting-deer':                                                  'Hunting - Deer',
        'hunting-duck':                                                  'Hunting - Duck',
        'hunting-turkey':                                                 'Hunting - Turkey',
        'parks-beach-scene':                                             'Parks - Beach Scene',
        'parks-bridge-scene':                                            'Parks - Bridge Scene',
        'parks-niagara-falls-scene':                                     'Parks - Niagara Falls Scene',
        # Sports
        'giants-super-bowl-champs-2012':                                 'Giants - Super Bowl Champs 2012',
        'nascar-dale-earnhardt-nascar-hall-of-fame':                     'NASCAR - Dale Earnhardt NASCAR Hall of Fame',
        'nascar-denny-hamlin':                                           'NASCAR - Denny Hamlin',
        'nascar-fan':                                                    'NASCAR Fan',
        'nascar-five-bar-plate':                                         'NASCAR - Five Bar Plate',
        'nascar-kevin-harvick':                                          'NASCAR - Kevin Harvick',
        'nascar-kyle-bush':                                              'NASCAR - Kyle Bush',
        'nascar-martin-truex-jr':                                        'NASCAR - Martin Truex Jr.',
        'nascar-richard-petty-historical':                               'NASCAR - Richard Petty Historical',
        'nascar-ross-chastain':                                          'NASCAR - Ross Chastain',
        'nascar-track-plate':                                            'NASCAR Track Plate',
        'new-york-yankees-world-series-champions-2009':                  'New York Yankees - World Series Champions 2009',
        'saratoga-cortez-horse-racing':                                  'Saratoga - Cortez Horse Racing',
        # Specialty
        'american-motorcyclists-assn':                                   'American Motorcyclists Association',
        'ancient-order-of-hiberians':                                    'Ancient Order of Hibernians',
        'bmw-car-club-of-america':                                       'BMW Car Club of America',
        'i-love-ny':                                                     'I Love NY',
        'land-surveyors-assn':                                           'Land Surveyors Association',
        'new-york-state-dental-association-dds':                         'New York State Dental Association (DDS)',
        'new-york-state-dental-association-dmd':                         'New York State Dental Association (DMD)',
        'optometrist-ophthalmic-dispenser-optician':                     'Optometrist / Ophthalmic Dispenser / Optician',
        'schenectady-proctors-theatre':                                  "Schenectady Proctor's Theatre",
        # Zodiac
        'zodiac-aquarius':    'Zodiac - Aquarius',
        'zodiac-aries':       'Zodiac - Aries',
        'zodiac-cancer':      'Zodiac - Cancer',
        'zodiac-capricorn':   'Zodiac - Capricorn',
        'zodiac-gemini':      'Zodiac - Gemini',
        'zodiac-leo':         'Zodiac - Leo',
        'zodiac-libra':       'Zodiac - Libra',
        'zodiac-pisces':      'Zodiac - Pisces',
        'zodiac-sagittarius': 'Zodiac - Sagittarius',
        'zodiac-scorpio':     'Zodiac - Scorpio',
        'zodiac-taurus':      'Zodiac - Taurus',
        'zodiac-virgo':       'Zodiac - Virgo',
        'life-pass-it-on':    'Life - Pass It On',
        # Occupational
        'chiropractor-dch':   'Chiropractor (DCH)',
        'chiropractor-nysca': 'Chiropractor (NYSCA)',
    }

    name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name = f'NY - {name_text}{v_suffix}{mc_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'ny-standard-issue':
        if '1986' in core:
            series = NY_STD_1986_SERIES
        elif '2001' in core:
            series = NY_STD_2001_SERIES
        elif '2010' in core:
            series = NY_STD_2010_SERIES
        else:
            series = NY_STD_2020_SERIES
        cat_id, cat_conf = CAT['Standard Issue'], 95

    elif sub == 'ny-non-passenger':
        if 'empire-gold' in core:
            series = NY_NP_GOLD_SERIES
        elif 'empire-state' in core:
            series = NY_NP_STATE_SERIES
        else:
            series = NY_NP_EXCELSIOR_SERIES
        if 'dealer' in core:
            vehicle_class = 'Passenger'
            cat_id, cat_conf = CAT['Dealer / Manufacturer'], 95
        elif 'trailer' in core:
            vehicle_class = 'Trailer'
            cat_id, cat_conf = CAT['Other / Specialty'], 85
        elif any(x in core for x in ('commercial', 'taxi', 'tow-truck')):
            vehicle_class = 'Commercial'
            cat_id, cat_conf = CAT['Other / Specialty'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'ny-military-veteran':
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif sub == 'ny-first-responder':
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'ny-fraternal':
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 95

    elif sub == 'ny-schools':
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif sub == 'ny-sports':
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 95

    elif sub == 'ny-outdoors':
        series = NY_SPECIALTY_SERIES
        if any(x in core for x in ('cayuga-nation', 'capital-region', 'central-new-york',
                                    'finger-lakes', 'long-island', 'mid-hudson', 'mohawk',
                                    'north-country', 'new-york-city-region', 'southern-tier',
                                    'western-new-york', 'discover-queens')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 80
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 92

    elif sub == 'ny-occupational':
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 90

    elif sub == 'ny-specialty':
        series = NY_SPECIALTY_SERIES
        if core.startswith('zodiac-'):
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        elif any(x in core for x in ('cancer', 'autism', 'down-syndrome', 'lupus',
                                    'sclerosis', 'diabetes', 'mental-health',
                                    'domestic-violence', 'drug-free', 'life-pass',
                                    'drive-for-the-cure', 'drive-out-diabetes',
                                    'organ-donor', 'paws-of-war')):
            cat_id, cat_conf = CAT['Health & Awareness'], 92
        elif 'ham-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif any(x in core for x in ('state-of-the-arts', 'theatre', 'theater',
                                      'cultural-institutions')):
            cat_id, cat_conf = CAT['Arts / Culture'], 90
        elif any(x in core for x in ('erie-canal', 'anniversary')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'agriculture' in core:
            cat_id, cat_conf = CAT['Agricultural'], 90
        elif any(x in core for x in ('ancient-order', 'operating-engineers',
                                      'united-teachers', 'bmw-car-club',
                                      'motorcyclists-assn', 'land-surveyors',
                                      'realtors', 'dental-association')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    else:
        series           = NY_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     33,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── NV parser ─────────────────────────────────────────────────────────────────
def parse_nv(stem: str, actual_filename: str):
    """Parse a single NV (Nevada) plate image from a flat (no-subfolder) folder.

    Series routing:
      nv-standard-issue-1969-*         → NV_STD_1969_SERIES (791)
      nv-standard-issue-1983-*         → NV_STD_1983_SERIES (790)
      nv-standard-issue-2001-*         → NV_STD_2001_SERIES (789)
      nv-standard-issue-2016-*         → NV_STD_2016_SERIES (788)  (non-passenger variants here too)
      nv-standard-issue-2016-civil-air-patrol → NV_MIL_SERIES (793)  (exception)
      nv-alternative-issue-2024-*      → NV_ALT_2024_SERIES (792)
      nv-veteran-*, military keywords  → NV_MIL_SERIES (793)
      all others                       → NV_SPECIALTY_SERIES (794)

    Date-range suffix handling:
      Trailing -YYYY-YYYY (e.g. -2013-2014) is stripped from the name.
      Single years in filenames (e.g. -2005) are NOT stripped.

    Vehicle class:
      nv-motorcycle-old-2005  → Motorcycle (explicit override)
      all others              → Passenger
    """
    if not stem.lower().startswith('nv-'):
        return None

    orig_stem = stem.lower()
    core_raw  = stem[3:]                                    # strip 'nv-'
    core_raw  = re.sub(r'-\d{4}-\d{4}$', '', core_raw)    # strip trailing year range
    core      = core_raw.lower()

    # ── v-suffix extraction ──────────────────────────────────────────────────
    v_suffix = ''
    v_match  = re.search(r'-(v\d+)$', core)
    if v_match:
        v_suffix  = f' - {v_match.group(1)}'
        core_raw  = core_raw[:v_match.start()]
        core      = core[:v_match.start()]

    # ── Special-case: motorcycle variant of current standard issue ───────────
    if orig_stem == 'nv-motorcycle-old-2005':
        suffix = actual_filename.split('.')[-1]
        return {
            'filename':      f'{stem}.{suffix}',
            'plate_name':    'NV - Standard Issue - Motorcycle',
            'slug':          slug_from_name('NV - Standard Issue - Motorcycle'),
            'category_id':   CAT['Standard Issue'],
            'category_conf': 90,
            'vehicle_class': 'Motorcycle',
            'series_id':     NV_STD_2016_SERIES['id'],
            'series_conf':   NV_STD_2016_SERIES['conf'],
            'region_id':     29,
            'notes':         [],
            'src_subfolder': '',
        }

    # ── Name overrides ───────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue multi-part names
        'standard-issue-1969-blue':               'Standard Issue - 1969 - Blue',
        'standard-issue-1983-big-horn':           'Standard Issue - 1983 - Big Horn Sheep',
        'standard-issue-2001-sunset':             'Standard Issue - 2001 - Sunset',
        'standard-issue-2016-accessible':         'Standard Issue - 2016 - Accessible',
        'standard-issue-2016-amateur-radio':      'Standard Issue - 2016 - Amateur Radio',
        'standard-issue-2016-antique-truck':      'Standard Issue - 2016 - Antique Truck',
        'standard-issue-2016-civil-air-patrol':   'Standard Issue - 2016 - Civil Air Patrol',
        'standard-issue-2016-exempt':             'Standard Issue - 2016 - Exempt',
        'standard-issue-2016-hall-of-fame':       'Standard Issue - 2016 - Hall of Fame',
        'standard-issue-2016-home':               'Standard Issue - 2016 - Home',
        'standard-issue-2016-horseless-carriage': 'Standard Issue - 2016 - Horseless Carriage',
        'standard-issue-2016-street-rod':         'Standard Issue - 2016 - Street Rod',
        # Alternative issue
        'alternative-issue-2024-blue-reissue':    'Alternative Issue - 2024 - 1969 Blue Reissue',
        # Military corrections
        'bronze-star-with-valor':                 'Bronze Star with Valor',
        'ex-prisoner-of-war':                     'Ex-Prisoner of War',
        'uss-nevada-battleship':                  'USS Nevada Battleship',
        'veteran-air-force':                      'Veteran - Air Force',
        'veteran-air-national-guard':             'Veteran - Air National Guard',
        'veteran-army':                           'Veteran - Army',
        'veteran-army-airborne':                  'Veteran - Army Airborne',
        'veteran-army-national-guard':            'Veteran - Army National Guard',
        'veteran-coast-guard':                    'Veteran - Coast Guard',
        'veteran-marine-corps':                   'Veteran - Marine Corps',
        'veteran-navy':                           'Veteran - Navy',
        'veteran-navy-seebees':                   'Veteran - Navy Seabees',
        'veteran-woman-vet':                      'Veteran - Woman Vet',
        # Specialty corrections
        'casa-childrens-advocates':               "CASA Children's Advocates",
        'divine-nine-hbcu-fraternaties':          'Divine Nine HBCU Fraternities',
        'friends-of-las-vegas-metro-pd':          'Friends of Las Vegas Metro PD',
        'stem-education':                         'STEM Education',
        'travelnevada':                           'TravelNevada',
        'unlv-collegiate':                        'UNLV Collegiate',
        'unr-collegiate':                         'UNR Collegiate',
        'womens-suffrage':                        "Women's Suffrage",
    }
    name_text     = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name    = f'NV - {name_text}{v_suffix}'
    vehicle_class = 'Passenger'

    # ── Military stems ───────────────────────────────────────────────────────
    MILITARY_STEMS = frozenset({
        'nv-bronze-star-with-valor',
        'nv-congressional-medal-of-honor',
        'nv-disabled-female-veteran',
        'nv-disabled-veteran-v1',
        'nv-disabled-veteran',
        'nv-ex-prisoner-of-war',
        'nv-fallen-military',
        'nv-gold-star',
        'nv-national-guard',
        'nv-pearl-harbor-survivor-veteran',
        'nv-purple-heart',
        'nv-retired-military',
        'nv-silver-star',
        'nv-standard-issue-2016-civil-air-patrol',
        'nv-uss-nevada-battleship',
        'nv-veteran-air-force',
        'nv-veteran-air-national-guard',
        'nv-veteran-army',
        'nv-veteran-army-airborne',
        'nv-veteran-army-national-guard',
        'nv-veteran-coast-guard',
        'nv-veteran-marine-corps',
        'nv-veteran-navy',
        'nv-veteran-navy-seebees',
        'nv-veteran-woman-vet',
    })

    # ── Series + category routing ────────────────────────────────────────────
    if orig_stem in MILITARY_STEMS:
        series           = NV_MIL_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif core.startswith('standard-issue-'):
        if '1969' in core:
            series = NV_STD_1969_SERIES
        elif '1983' in core:
            series = NV_STD_1983_SERIES
        elif '2001' in core:
            series = NV_STD_2001_SERIES
        else:
            series = NV_STD_2016_SERIES

        if 'accessible' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'exempt' in core:
            cat_id, cat_conf = CAT['Government / Exempt'], 90
        elif any(x in core for x in ('hall-of-fame', 'horseless-carriage', 'antique-truck', 'street-rod')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif core.startswith('alternative-issue-'):
        series           = NV_ALT_2024_SERIES
        cat_id, cat_conf = CAT['Standard Issue'], 95

    else:
        series = NV_SPECIALTY_SERIES
        if any(x in core for x in ('cancer', 'autism', 'organ-donor', 'casa', 'missing-and-exploited',
                                    'supporting-healthcare', 'opportunity-village', 'children-in-the-arts')):
            cat_id, cat_conf = CAT['Health & Awareness'], 92
        elif any(x in core for x in ('wildlife', 'conservation', 'bighorns', 'ducks-unlimited',
                                      'horse-power', 'starry-skies', 'mustangs', 'lake-tahoe',
                                      'pyramid-lake', 'red-rock-canyon')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 92
        elif any(x in core for x in ('raiders', 'golden-knights', 'ultimate-fighting', 'rodeo',
                                      'unlv-collegiate', 'unr-collegiate',
                                      'reno-air-races', 'great-reno-air-race')):
            cat_id, cat_conf = CAT['Sports Team'], 92
        elif any(x in core for x in ('agriculture', 'future-farmers')):
            cat_id, cat_conf = CAT['Agricultural'], 90
        elif any(x in core for x in ('masonic', 'carpenters-union', 'teamsters', 'divine-nine',
                                      'eagle-scout', 'girl-scout')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 90
        elif any(x in core for x in ('firefighter', 'fire-truck', 'decorated-peace-officer',
                                      'metro-pd', 'search-and-rescue')):
            cat_id, cat_conf = CAT['First Responder'], 92
        elif any(x in core for x in ('anniversary', 'las-vegas-commemorative', 'mob-museum',
                                      'nevada-test-site', 'hoover-dam', 'virginia-truckee-railroad',
                                      'sparks-heritage', 'henderson', 'outside-las-vegas',
                                      'las-vegas-springs', 'travelnevada', 'mount-charleston',
                                      'hot-august-nights', 'aviation', 'air-force-thunderbirds',
                                      'airport-managers')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     29,
        'notes':         [],
        'src_subfolder': '',
    }


# ── NM parser ─────────────────────────────────────────────────────────────────
def parse_nm(stem: str, subfolder: str, actual_filename: str):
    """Parse a single NM (New Mexico) plate image across 6 subfolders.

    Series routing:
      nm-standard-issue  → NM_STD_SERIES (779) for standard issue + misc variants
                         → NM_ALT_BALL_SERIES (786) for alternative-issue-1999-balloon
                         → NM_ALT_CENT_SERIES (781) for alternative-issue-2010-centennial
                         → NM_ALT_TURQ_SERIES (780) for alternative-issue-2016-turquoise
                         → NM_ALT_CHIL_SERIES (782) for alternative-issue-2017-chile(s)
      nm-veteran-military→ NM_MIL_SERIES (783)
      nm-specialty       → NM_SPECIALTY_SERIES (785)
      nm-first-responder → NM_SPECIALTY_SERIES (785)
      nm-outdoors        → NM_SPECIALTY_SERIES (785)
      nm-schools         → NM_SPECIALTY_SERIES (785)

    Vehicle class notes:
      nm-veteran-motorcycle              → Motorcycle
      nm-childrens-trust-fund-motorcycle → Motorcycle
      nm-disabled-person, nm-horseless-carriage → Other
    """
    if not stem.lower().startswith('nm-'):
        return None

    core_raw = stem[3:]   # strip 'nm-' prefix
    core     = core_raw.lower()

    # ── Full-stem overrides (non-Passenger class without motorcycle suffix) ──
    FULL_STEM = {
        'nm-disabled-person':    ('NM - Disabled Person',    'Other'),
        'nm-horseless-carriage': ('NM - Horseless Carriage', 'Other'),
    }
    if stem.lower() in FULL_STEM:
        plate_name, vehicle_class = FULL_STEM[stem.lower()]
    else:
        # ── Motorcycle detection ─────────────────────────────────────────────
        if core.endswith('-motorcycle'):
            vehicle_class = 'Motorcycle'
            core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
            core     = core_raw.lower()
            moto_suffix = ' - Motorcycle'
        else:
            vehicle_class = 'Passenger'
            moto_suffix   = ''

        NAME_OVERRIDES = {
            # Standard issue multi-part names
            'standard-issue-1990-yellow':        'Standard Issue - 1990 - Yellow',
            'alternative-issue-1999-balloon':    'Alternative Issue - 1999 - Balloon',
            'alternative-issue-2010-centennial': 'Alternative Issue - 2010 - Centennial',
            'alternative-issue-2016-turquoise':  'Alternative Issue - 2016 - Turquoise',
            'alternative-issue-2017-chile':      'Alternative Issue - 2017 - Chilies',
            # Acronyms / abbreviations
            'amateur-radio-operator':            'Amateur Radio Operator',
            'emergency-medical-technicians-emt': 'Emergency Medical Technicians (EMT)',
            'fraternal-order-of-police':         'Fraternal Order of Police',
            'retired-nm-state-police':           'Retired NM State Police',
            # Punctuation fixes
            'childrens-trust-fund':              "Children's Trust Fund",
            '100-disabled-veteran':              '100% Disabled Veteran',
            'disabled-veteran-wheelchair':       'Disabled Veteran - Wheelchair',
        }
        name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
        plate_name = f'NM - {name_text}{moto_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'nm-standard-issue':
        if '1999' in core:
            series = NM_ALT_BALL_SERIES
        elif '2010' in core:
            series = NM_ALT_CENT_SERIES
        elif '2016' in core:
            series = NM_ALT_TURQ_SERIES
        elif '2017' in core:
            series = NM_ALT_CHIL_SERIES
        else:
            series = NM_STD_SERIES

        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif 'horseless' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif subfolder == 'nm-veteran-military':
        series           = NM_MIL_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'nm-first-responder':
        series           = NM_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 92

    elif subfolder == 'nm-outdoors':
        series = NM_SPECIALTY_SERIES
        if 'farm-and-ranch' in core:
            cat_id, cat_conf = CAT['Agricultural'], 90
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 92

    elif subfolder == 'nm-schools':
        series           = NM_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 92

    elif subfolder == 'nm-specialty':
        series = NM_SPECIALTY_SERIES
        if any(x in core for x in ('cancer', 'organ-donor', 'autism', 'adopt-a-child', 'childrens-trust')):
            cat_id, cat_conf = CAT['Health & Awareness'], 92
        elif any(x in core for x in ('santa-fe', 'cumbres', 'boy-scouts', 'route-66', 'las-cruces')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 85

    else:
        series           = NM_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     32,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── NJ parser ─────────────────────────────────────────────────────────────────
def parse_nj(stem: str, subfolder: str, actual_filename: str):
    """Parse a single NJ (New Jersey) plate image across 9 subfolders.

    Series routing:
      nj-standard-issue           → NJ_STD_SERIES (775) — all files incl. misplaced variants
      nj-non-passenger-government → NJ_NON_PASS_SERIES (776), Other class
      nj-specialty                → NJ_SPECIALTY_SERIES (777)
      nj-first-responder          → NJ_SPECIALTY_SERIES (777)
      nj-fraternal                → NJ_SPECIALTY_SERIES (777)
      nj-outdoors                 → NJ_SPECIALTY_SERIES (777)
      nj-schools                  → NJ_SPECIALTY_SERIES (777)
      nj-sports                   → NJ_SPECIALTY_SERIES (777)
      nj-military-veteran         → NJ_MIL_SERIES (778)

    Vehicle class notes:
      nj-non-passenger-government → Other
      nj-treasure-our-trees-commercial → Other
      nj-handicapped, nj-wheelchair-symbol-plates → Other
      all others → Passenger
    """
    if not stem.lower().startswith('nj-'):
        return None

    core_raw = stem[3:]   # strip 'nj-' prefix
    core     = core_raw.lower()

    # ── Full-stem overrides ───────────────────────────────────────────────────
    FULL_STEM = {
        'nj-handicapped':                   ('NJ - Handicapped',                    'Other'),
        'nj-wheelchair-symbol-plates':      ('NJ - Wheelchair Symbol Plates',       'Other'),
        'nj-treasure-our-trees-commercial': ('NJ - Treasure Our Trees - Commercial','Other'),
    }
    if stem.lower() in FULL_STEM:
        plate_name, vehicle_class = FULL_STEM[stem.lower()]
    else:
        vehicle_class = 'Passenger'
        NAME_OVERRIDES = {
            # Standard issue
            'standard-issue-1992':                    'Standard Issue - 1992',
            # Acronyms / abbreviations
            'emt-a':                                  'EMT-A',
            'npdf-safe-cop':                          'NPDF Safe Cop',
            'newark-f-f':                             'Newark FF',
            'amvets':                                 'AMVETS',
            'p-o-w':                                  'POW',
            'usaf-reserve':                           'USAF Reserve',
            'usaf-retired':                           'USAF Retired',
            'u-s-army-retired':                       'US Army Retired',
            'uscg-auxiliary':                         'USCG Auxiliary',
            'uscg-reserve':                           'USCG Reserve',
            'usmc-reserve':                           'USMC Reserve',
            'usn-reserve':                            'USN Reserve',
            'uss-new-jersey-battleship':              'USS New Jersey Battleship',
            'vfw-of-the-us':                          'VFW of the US',
            'state-f-m-b-a':                          'State FMBA',
            'state-f-o-p':                            'State FOP',
            'state-p-b-a':                            'State PBA',
            # NY prefix
            'ny-giants':                              'NY Giants',
            'ny-jets':                                'NY Jets',
            'ny-knicks':                              'NY Knicks',
            'ny-mets':                                'NY Mets',
            'ny-yankees':                             'NY Yankees',
            'ny-press':                               'NY Press',
            # "and" insertions / corrections
            'air-army-guard':                         'Air and Army Guard',
            'deborah-heart-lung':                     'Deborah Heart and Lung',
            # NJ capitalisation
            'discover-nj-history':                    'Discover NJ History',
            # Abbreviated titles
            'firefighter-int-l':                      "Firefighter Int'l",
            'physician-md':                           'Physician MD',
            'physician-osteopathic':                  'Osteopathic Physician',
            'dentist-dds':                            'Dentist DDS',
            'dentist-dmd':                            'Dentist DMD',
            # NASCAR series
            'nascar':                                 'NASCAR',
            'nascar-dale-earnhardt-hall-of-fame':     'NASCAR - Dale Earnhardt - Hall of Fame',
            'nascar-dale-earnhardt-jr':               'NASCAR - Dale Earnhardt Jr',
            'nascar-dale-earnhardt-sr':               'NASCAR - Dale Earnhardt Sr',
            'nascar-danica-patrick':                  'NASCAR - Danica Patrick',
            'nascar-ford-racing':                     'NASCAR - Ford Racing',
            'nascar-jeff-gordon':                     'NASCAR - Jeff Gordon',
            'nascar-jimmie-johnson':                  'NASCAR - Jimmie Johnson',
            'nascar-kevin-harvick':                   'NASCAR - Kevin Harvick',
            'nascar-martin-truex-jr':                 'NASCAR - Martin Truex Jr',
            'nascar-tony-stewart':                    'NASCAR - Tony Stewart',
        }
        name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
        plate_name = f'NJ - {name_text}'

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'nj-standard-issue':
        series = NJ_STD_SERIES
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'handicap' in core or 'wheelchair' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif 'standard-issue' in core:
            cat_id, cat_conf = CAT['Standard Issue'], 95
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 85

    elif subfolder == 'nj-non-passenger-government':
        series        = NJ_NON_PASS_SERIES
        vehicle_class = 'Other'
        if 'ambulance' in core:
            cat_id, cat_conf = CAT['First Responder'], 95
        elif 'dealer' in core:
            cat_id, cat_conf = CAT['Dealer / Manufacturer'], 90
        elif 'farm' in core:
            cat_id, cat_conf = CAT['Agricultural'], 90
        else:
            cat_id, cat_conf = CAT['Government / Exempt'], 88

    elif subfolder == 'nj-military-veteran':
        series           = NJ_MIL_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'nj-specialty':
        series = NJ_SPECIALTY_SERIES
        if any(x in core for x in ('cancer', 'organ-donor', 'deborah-heart', 'conquer')):
            cat_id, cat_conf = CAT['Health & Awareness'], 92
        elif 'agriculture' in core:
            cat_id, cat_conf = CAT['Agricultural'], 90
        elif any(x in core for x in ('discover-nj-history', 'historic')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        elif 'square-dancer' in core:
            cat_id, cat_conf = CAT['Arts / Culture'], 88
        elif any(x in core for x in ('teamsters', 'operating-engineers')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 85

    elif subfolder == 'nj-first-responder':
        series = NJ_SPECIALTY_SERIES
        if 'press' in core:
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        else:
            cat_id, cat_conf = CAT['First Responder'], 92

    elif subfolder == 'nj-fraternal':
        series = NJ_SPECIALTY_SERIES
        if any(x in core for x in ('f-o-p', 'p-b-a')):
            cat_id, cat_conf = CAT['First Responder'], 90
        else:
            cat_id, cat_conf = CAT['Fraternal / Civic'], 92

    elif subfolder == 'nj-outdoors':
        series = NJ_SPECIALTY_SERIES
        if 'bowhunters' in core:
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 92

    elif subfolder == 'nj-schools':
        series           = NJ_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 92

    elif subfolder == 'nj-sports':
        series           = NJ_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 92

    else:
        series           = NJ_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     31,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── NE parser ─────────────────────────────────────────────────────────────────
def parse_ne(stem: str, subfolder: str, actual_filename: str):
    """Parse a single NE (Nebraska) plate image across 8 subfolders.

    Series routing:
      ne-standard-issue (year files)  → year-based series 763–767 (one plate per series)
      ne-standard-issue (other files) → NE_SPECIALTY_SERIES (768)
      ne-first-responder              → NE_SPECIALTY_SERIES (768), First Responder
      ne-military-veteran             → NE_MILITARY_SERIES (769), Military / Veteran
      ne-non-passenger                → NE_NON_PASS_SERIES (770), Government / Exempt
      ne-outdoor                      → NE_SPECIALTY_SERIES (768), Conservation keyword routing
      ne-schools                      → NE_SPECIALTY_SERIES (768), School
      ne-specialty                    → NE_SPECIALTY_SERIES (768), keyword routing

    Files not starting with 'ne-' (e.g. aa-blank-license-plate-renamer.png) are skipped.
    Nebraska has no motorcycle variants.
    """
    if not stem.lower().startswith('ne-'):
        return None

    core_raw = stem[3:]   # strip 'ne-' prefix
    core     = core_raw.lower()
    vehicle_class = 'Passenger'

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue — multi-part qualifiers with ' - ' separators
        # Note: file is misspelled 'sequicentennial'; correct name has 'ses' prefix
        'standard-issue-2023-genius':               'Standard Issue - 2023 - Genius',
        'standard-issue-2017-sequicentennial':       'Standard Issue - 2017 - Sesquicentennial',
        'standard-issue-2011-meadowlark':            'Standard Issue - 2011 - Meadowlark',
        'standard-issue-2005-conestoga':             'Standard Issue - 2005 - Conestoga',
        # File named 'sunset' informally; official name is Prairie River
        'standard-issue-2002-sunset':               'Standard Issue - 2002 - Prairie River',
        # Military — US branches, no periods
        'us-air-force':                             'US Air Force',
        'us-air-force-reserve':                     'US Air Force Reserve',
        'us-air-national-guard':                    'US Air National Guard',
        'us-army':                                  'US Army',
        'us-army-reserve':                          'US Army Reserve',
        'us-coast-guard':                           'US Coast Guard',
        'us-coast-guard-reserve':                   'US Coast Guard Reserve',
        'us-marine-corps':                          'US Marine Corps',
        'us-marine-corps-reserve':                  'US Marine Corps Reserve',
        'us-national-guard':                        'US National Guard',
        'us-navy':                                  'US Navy',
        'us-navy-reserve':                          'US Navy Reserve',
        # Outdoor — drop corporate suffix; restructure wildlife series
        'ducks-unlimited-inc':                      'Ducks Unlimited',
        'friends-of-the-union-pacific-rr-museum':   'Friends of the Union Pacific RR Museum',
        'wildlife-conservation-plates-bighorn-sheep':      'Wildlife Conservation - Bighorn Sheep',
        'wildlife-conservation-plates-ornate-box-turtle':  'Wildlife Conservation - Ornate Box Turtle',
        'wildlife-conservation-plates-sandhill-crane':     'Wildlife Conservation - Sandhill Crane',
        'josh-the-otter-be-safe-around-water':      'Josh the Otter - Be Safe Around Water',
        'corn-growers-association':                 'Corn Growers Assn',
    }
    name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name = f'NE - {name_text}'

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'ne-standard-issue':
        cat_id, cat_conf = CAT['Standard Issue'], 95
        if '2023' in core:
            series = NE_STD_2023_SERIES
        elif '2017' in core:
            series = NE_STD_2017_SERIES
        elif '2011' in core:
            series = NE_STD_2011_SERIES
        elif '2005' in core:
            series = NE_STD_2005_SERIES
        elif '2002' in core:
            series = NE_STD_2002_SERIES
        else:
            # Non-year variants → specialty series with refined categories
            series = NE_SPECIALTY_SERIES
            if 'handicapped' in core:
                cat_id, cat_conf = CAT['Government / Exempt'], 90
                vehicle_class    = 'Other'
            elif 'non-resident' in core:
                cat_id, cat_conf = CAT['Government / Exempt'], 90
            elif 'historical' in core:
                cat_id, cat_conf = CAT['Historical / Commemorative'], 85
            else:
                cat_id, cat_conf = CAT['Other / Specialty'], 72

    elif subfolder == 'ne-first-responder':
        series           = NE_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'ne-military-veteran':
        series           = NE_MILITARY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'ne-non-passenger':
        series           = NE_NON_PASS_SERIES
        cat_id, cat_conf = CAT['Government / Exempt'], 90
        vehicle_class    = 'Other'

    elif subfolder == 'ne-outdoor':
        series           = NE_SPECIALTY_SERIES
        if any(kw in core for kw in ('ducks', 'mountain-lion', 'wildlife', 'conservation')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 95
        elif any(kw in core for kw in ('josh', 'otter', 'good-life')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 85
        elif 'zoo' in core:
            cat_id, cat_conf = CAT['Arts / Culture'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    elif subfolder == 'ne-schools':
        series           = NE_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    else:  # ne-specialty and catch-all
        series           = NE_SPECIALTY_SERIES
        if any(kw in core for kw in ('cancer', 'donate-life', 'down-syndrome', 'nursing')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif any(kw in core for kw in ('czech', 'native-american', 'history', 'union-pacific', 'arbor-day')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif 'arts' in core:
            cat_id, cat_conf = CAT['Arts / Culture'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     28,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── ND parser ─────────────────────────────────────────────────────────────────
def parse_nd(stem: str, subfolder: str, actual_filename: str):
    """Parse a single ND (North Dakota) plate image across 8 subfolders.

    Series routing:
      nd-standard-issue  → ND_STD_SERIES (759) base Legendary/mobility-impaired
                         → ND_VINTAGE_SERIES (760) for antique/collector
                         → ND_BLACKOUT_SERIES (761) for blackout variants
      all other subfolders → ND_SPECIALTY_SERIES (762)

    Category routing:
      nd-first-responder → First Responder (95%)
      nd-military        → Military / Veteran (95%)
      nd-non-passenger   → Government / Exempt (90%), vehicle Other
      nd-outdoors        → Conservation / Environment (95%)
      nd-schools         → School (95%)
      nd-sports          → Sports Team (90%)
      nd-standard-issue  → Standard Issue (95%)
      nd-specialty       → keyword-based
    """
    if not stem.lower().startswith('nd-'):
        return None

    core_raw = stem[3:]   # strip 'nd-' prefix
    core     = core_raw.lower()

    # ── Full-stem overrides (name + vehicle_class set explicitly) ─────────────
    # Used when the suffix is part of the plate type name, not a generic descriptor.
    FULL_STEM = {
        'nd-antique-motorcycle':             ('ND - Antique Motorcycle',               'Motorcycle'),
        'nd-standard-issue-2015-motorcycle': ('ND - Standard Issue - 2015 - Motorcycle','Motorcycle'),
        'nd-blackout-motorcycle':            ('ND - Blackout - Motorcycle',             'Motorcycle'),
        'nd-blackout-mobility-impaired':     ('ND - Blackout - Mobility Impaired',      'Other'),
    }
    if stem.lower() in FULL_STEM:
        plate_name, vehicle_class = FULL_STEM[stem.lower()]
        moto_suffix = ''
    else:
        # ── Motorcycle detection ──────────────────────────────────────────────
        if core.endswith('-motorcycle'):
            vehicle_class = 'Motorcycle'
            core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
            core     = core_raw.lower()
            moto_suffix = ' - Motorcycle'
        else:
            vehicle_class = 'Passenger'
            moto_suffix   = ''

        # ── Name overrides ────────────────────────────────────────────────────
        NAME_OVERRIDES = {
            # Standard issue naming — multi-part qualifiers use ' - ' separator
            'standard-issue-2015-legendary':          'Standard Issue - 2015 - Legendary',
            'alternative-issue-2025-blackout':        'Alternative Issue - 2025 - Blackout',
            # Military — natural branch-first order
            'veteran-air-force':                      'Air Force Veteran',
            'veteran-army':                           'Army Veteran',
            'veteran-coast-guard':                    'Coast Guard Veteran',
            'veteran-marine':                         'Marine Veteran',
            'veteran-navy':                           'Navy Veteran',
            'veteran-space-force':                    'Space Force Veteran',
            'veteran-non-branch':                     'Veteran',
            'veteran-purple-heart':                   'Purple Heart',
            'gold-star-family-plate':                 'Gold Star Family',
            # Schools — acronyms must be all-caps
            'dsu':                                    'DSU',
            'msu':                                    'MSU',
            'ndsu':                                   'NDSU',
            'vcsu':                                   'VCSU',
            # Non-passenger
            'atv-off-highway':                        'ATV Off Highway',
            # Specialty — double nd- prefix, acronyms, hall of fame
            'nd-bowhunters-association':              'ND Bowhunters Assn',
            'nd-cowboy-hall-of-fame':                 'ND Cowboy - Hall of Fame',
            'hit-inc':                                'HIT Inc',
        }
        name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
        plate_name = f'ND - {name_text}{moto_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    if subfolder == 'nd-standard-issue':
        cat_id, cat_conf = CAT['Standard Issue'], 95
        # Series routing within standard-issue subfolder
        if 'blackout' in core:
            series = ND_BLACKOUT_SERIES
        elif 'antique' in core or core == 'collector':
            series = ND_VINTAGE_SERIES
        else:
            series = ND_STD_SERIES
        # Vehicle class refinement
        if 'antique' in core and vehicle_class != 'Motorcycle':
            vehicle_class = 'Other'
        elif 'mobility-impaired' in core:
            vehicle_class = 'Other'

    elif subfolder == 'nd-first-responder':
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif subfolder == 'nd-military':
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'nd-non-passenger':
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Government / Exempt'], 90
        vehicle_class    = 'Other'

    elif subfolder == 'nd-outdoors':
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 95

    elif subfolder == 'nd-schools':
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'nd-sports':
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:  # nd-specialty and catch-all
        series           = ND_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72
        # Keyword-based refinement
        if any(kw in core for kw in ('nursing', 'medical', 'sanford')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif any(kw in core for kw in ('veteran', 'military')):
            cat_id, cat_conf = CAT['Military / Veteran'], 90
        elif any(kw in core for kw in ('eagle', 'bowhunter', 'wildlife')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 85
        elif any(kw in core for kw in ('cowboy-hall', 'flag')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     35,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── GA parser ─────────────────────────────────────────────────────────────────
def parse_ga(stem: str, subfolder: str, actual_filename: str):
    """Parse a single GA (Georgia) plate image across 9 subfolders.

    Series routing:
      ga-non-passenger (exc. retired-legislators-emeritus) → GA_SERIES_NON_PASS (688)
      ga-standard-issue / standard-issue-2012-alternate   → GA_SERIES_PRESTIGE (686)
      ga-standard-issue (all other)                       → GA_SERIES_STANDARD (685)
      all other subfolders                                → GA_SERIES_SPECIALTY (687)

    Category routing:
      ga-first-responder → First Responder (95%)
      ga-fraternal       → Fraternal / Civic (88%)
      ga-outdoors        → Conservation / Environment (90%)
      ga-schools         → School (95%)
      ga-sports          → Sports Team (90%)
      ga-veteran         → Military / Veteran (95%)
      ga-standard-issue  → keyword overrides (radio, disabled, antique, standard-issue)
      ga-non-passenger   → ambulance/hearse-ambulance → First Responder (88%);
                           retired-legislators-emeritus → Other/Specialty to 687;
                           rest → Other/Specialty (72%)
      ga-specialty       → keyword rules

    Vehicle class:
      ga-non-passenger (exc. retired-legislators-emeritus) → Other
      'motorcycle' in filename → Motorcycle
      default → Passenger
    """
    if not stem.lower().startswith('ga-'):
        return None

    core_raw = stem[3:]           # strip 'ga-', preserve case
    core     = core_raw.lower()   # lowercase for matching

    # Strip double 'ga-' prefix (e.g. ga-ga-council-on-substance-abuse)
    if core.startswith('ga-'):
        core_raw = core_raw[3:]
        core     = core[3:]

    # Strip version suffix (-v1, -v2, etc.)
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version  = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core     = core[:vm.start()]

    # Convert '-amp-' → '-&-' for display names, then re-derive core
    core_raw = core_raw.replace('-amp-', '-&-')
    core     = core_raw.lower()

    if 'motorcycle' in core:
        vehicle_class = 'Motorcycle'
        # Strip '-motorcycle' suffix so name becomes "GA - Desert Storm - Motorcycle"
        core_raw = re.sub(r'-motorcycle$', '', core_raw, flags=re.IGNORECASE)
        core     = core_raw.lower()
        moto_suffix = ' - Motorcycle'
    else:
        vehicle_class = 'Passenger'
        moto_suffix   = ''

    # ── Non-passenger subfolder ────────────────────────────────────────────────
    if subfolder == 'ga-non-passenger':
        if core == 'retired-legislators-emeritus':
            # Passenger specialty plate filed in non-passenger — route to 687
            cat_id, cat_conf = CAT['Other / Specialty'], 72
            series = GA_SERIES_SPECIALTY
            # vehicle_class stays Passenger
        else:
            if 'ambulance' in core:
                cat_id, cat_conf = CAT['First Responder'], 88
            else:
                cat_id, cat_conf = CAT['Other / Specialty'], 72
            series        = GA_SERIES_NON_PASS
            vehicle_class = 'Other'

    # ── Standard-issue subfolder ───────────────────────────────────────────────
    elif subfolder == 'ga-standard-issue':
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
            series = GA_SERIES_STANDARD
        elif 'disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
            series = GA_SERIES_STANDARD
        elif 'antique' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
            series = GA_SERIES_STANDARD
        elif core == 'standard-issue-2012-alternate':
            cat_id, cat_conf = CAT['Standard Issue'], 95
            series = GA_SERIES_PRESTIGE
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95
            series = GA_SERIES_STANDARD

    # ── Direct subfolder → category mappings ──────────────────────────────────
    elif subfolder == 'ga-first-responder':
        cat_id, cat_conf = CAT['First Responder'], 95
        series = GA_SERIES_SPECIALTY

    elif subfolder == 'ga-fraternal':
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88
        series = GA_SERIES_SPECIALTY

    elif subfolder == 'ga-outdoors':
        cat_id, cat_conf = CAT['Conservation / Environment'], 90
        series = GA_SERIES_SPECIALTY

    elif subfolder == 'ga-schools':
        cat_id, cat_conf = CAT['School'], 95
        series = GA_SERIES_SPECIALTY

    elif subfolder == 'ga-sports':
        cat_id, cat_conf = CAT['Sports Team'], 90
        series = GA_SERIES_SPECIALTY

    elif subfolder == 'ga-veteran':
        cat_id, cat_conf = CAT['Military / Veteran'], 95
        series = GA_SERIES_SPECIALTY

    else:  # ga-specialty (and any unexpected subfolder)
        series = GA_SERIES_SPECIALTY
        if any(kw in core for kw in ['cancer', 'choose-life', 'substance-abuse',
                                      'nurses', 'grady-health', 'healthcare',
                                      'shepherd-center', 'sickle-cell']):
            cat_id, cat_conf = CAT['Health & Awareness'], 88
        elif any(kw in core for kw in ['zoo', 'recycle', 'pet', 'dog', 'feline',
                                        'alternative-fuel']):
            cat_id, cat_conf = CAT['Conservation / Environment'], 90
        elif any(kw in core for kw in ['historic', 'hall-of-fame', 'seniquimcentennial']):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    name_text  = to_title(core_raw)
    plate_name = f'GA - {name_text}{moto_suffix}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── DC parser ─────────────────────────────────────────────────────────────────
def parse_dc(stem: str, subfolder: str, actual_filename: str):
    """Parse a single DC (Washington, D.C.) plate image across 7 subfolders.

    Series routing: all plates → DC_SERIES (681)

    Category routing:
      dc-fraternal     → Fraternal / Civic (88%)
      dc-outdoors      → Conservation / Environment (90%)
      dc-schools       → School (95%)
      dc-sports        → Sports Team (90%)
      dc-veteran       → Military / Veteran (95%); '-symbol' suffix → Disabled/Accessibility
      dc-standard-issue→ Standard Issue (95%)
      dc-specialty     → keyword rules → DC_SPECIALTY_RULES

    Filename normalisation:
      Double 'dc-' prefix stripped (e.g. dc-dc-veteran-tags → Veteran Tags)
      '-note-...' annotation suffix stripped (filename notes baked into filename)

    Known skipped files:
      dc-specialty/dc-standard-issue-2017.png — duplicate of dc-standard-issue copy
    """
    if not actual_filename.lower().startswith('dc-'):
        return None

    # Skip the misplaced standard-issue plate in dc-specialty
    if subfolder == 'dc-specialty' and 'standard-issue' in stem.lower():
        return None

    core_raw = stem[3:]           # strip leading 'dc-', preserve case
    core     = core_raw.lower()

    # Strip double dc- prefix (e.g. dc-dc-veteran-tags → veteran-tags)
    if core.startswith('dc-'):
        core_raw = core_raw[3:]
        core     = core[3:]

    # Strip '-note-...' annotation suffix baked into filename
    note_m = re.search(r'-note-', core)
    if note_m:
        core_raw = core_raw[:note_m.start()]
        core     = core[:note_m.start()]

    vehicle_class = 'Passenger'

    if subfolder == 'dc-fraternal':
        cat_id, cat_conf = CAT['Fraternal / Civic'], 88

    elif subfolder == 'dc-outdoors':
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'dc-schools':
        cat_id, cat_conf = CAT['School'], 95

    elif subfolder == 'dc-sports':
        cat_id, cat_conf = CAT['Sports Team'], 90

    elif subfolder == 'dc-veteran':
        if core.endswith('-symbol'):
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'dc-standard-issue':
        cat_id, cat_conf = CAT['Standard Issue'], 95

    else:  # dc-specialty (and any unexpected subfolder)
        cat_id, cat_conf = DC_SPECIALTY_DEFAULT
        for keywords, cid, conf in DC_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text  = to_title(core_raw)
    plate_name = f'DC - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     DC_SERIES['id'],
        'series_conf':   DC_SERIES['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── CT parser ─────────────────────────────────────────────────────────────────
def parse_ct(stem: str, subfolder: str, actual_filename: str):
    """Parse a single CT (Connecticut) plate image across 8 subfolders.

    Series routing:
      ct-standard-issue containing '1987' in filename → CT_1987_SERIES (680)
      everything else                                  → CT_2000_SERIES (679)

    Category routing:
      ct-fraternal     → Fraternal / Civic (88%)
      ct-non-passenger → Other / Specialty (78%), vehicle class Other
      ct-outdoor       → Conservation / Environment (90%)
      ct-schools       → School (95%)
      ct-sports        → Sports Team (90%)
      ct-veteran       → Military / Veteran (95%)
      ct-standard-issue→ keyword overrides (radio, classic, motorcycle)
      ct-specialty     → keyword rules → CT_SPECIALTY_RULES

    Vehicle class:
      ct-non-passenger subfolder → Other
      'motorcycle' in filename   → Motorcycle
      default                    → Passenger
    """
    if not stem.lower().startswith('ct-'):
        return None

    core_raw = stem[3:]           # strip 'ct-', preserve case
    core     = core_raw.lower()   # lowercase for matching

    # Vehicle class
    if subfolder == 'ct-non-passenger':
        vehicle_class = 'Other'
    elif 'motorcycle' in core:
        vehicle_class = 'Motorcycle'
    else:
        vehicle_class = 'Passenger'

    # Default series — overridden only for the 1987 plate
    series = CT_1987_SERIES if '1987' in core else CT_2000_SERIES

    # Category routing
    subcat = CT_SUBFOLDER_CATEGORIES.get(subfolder)
    if subcat is not None:
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']

    elif subfolder == 'ct-standard-issue':
        if 'amateur-radio' in core or 'ham-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'classic-vehicle' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    else:  # ct-specialty (and any unexpected subfolder)
        cat_id, cat_conf = CT_SPECIALTY_DEFAULT
        for keywords, cid, conf in CT_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text  = to_title(core_raw)
    plate_name = f'CT - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── BC parser ─────────────────────────────────────────────────────────────────
def parse_bc(stem: str, subfolder: str, actual_filename: str):
    """Parse a single BC (British Columbia) plate image across 5 subfolders.

    Series routing:
      bc-non-passenger   → BC_NP_SERIES (678), vehicle class Other
      bc-outdoors        → BC_SPECIALTY_SERIES (677), Conservation/Environment
      bc-veteran         → BC_SPECIALTY_SERIES (677), Military/Veteran
      bc-specialty       → BC_SPECIALTY_SERIES (677), keyword-derived category
      bc-standard-issue  → BC_STD_ISSUE_SERIES (676), keyword-derived category/class

    Filename normalisation:
      Underscores in stem replaced with hyphens (bc-farm_truck → bc-farm-truck)

    Known skipped files:
      IMG_6186.JPG — no bc- prefix; will appear in skipped list
      BC-parks-licence-plate-porteau-cove-LARGE.png — high-res duplicate of
        bc-porteau-cove.png; will appear in skipped list
    """
    if not actual_filename.lower().startswith('bc-'):
        return None   # e.g. IMG_6186.JPG

    if 'LARGE' in actual_filename:
        return None   # BC-parks-licence-plate-porteau-cove-LARGE.png

    core_raw = stem[3:].replace('_', '-')   # strip 'bc-', normalise underscores
    core     = core_raw.lower()

    vehicle_class = 'Passenger'

    if subfolder == 'bc-non-passenger':
        vehicle_class    = 'Other'
        series           = BC_NP_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 78

    elif subfolder == 'bc-veteran':
        series           = BC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif subfolder == 'bc-outdoors':
        series           = BC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 90

    elif subfolder == 'bc-specialty':
        series = BC_SPECIALTY_SERIES
        if 'olympics' in core:
            cat_id, cat_conf = CAT['Sports Team'], 90
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 72

    else:  # bc-standard-issue (and any unexpected subfolder)
        series = BC_STD_ISSUE_SERIES
        if 'ham-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'collector-vehicle' in core or 'vintage-vehicle' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'farm' in core:
            cat_id, cat_conf = CAT['Agricultural'], 88
            vehicle_class    = 'Other'
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95
        if 'truck' in core and 'farm' not in core:
            vehicle_class = 'Other'

    name_text  = to_title(core_raw)
    plate_name = f'BC - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── AK parser ─────────────────────────────────────────────────────────────────
def parse_ak(stem: str, subfolder: str, actual_filename: str):
    """Parse a single AK (Alaska) plate image across 5 subfolders.

    Series routing:
      ak-standard-issue → AK_STD_ISSUE_SERIES (657), keyword-based category
      all other subfolders → AK_SPECIALTY_SERIES (658)

    Vehicle class:
      ak-non-passenger subfolder → Other
      'motorcycle' in filename → Motorcycle
      default → Passenger
    """
    if not stem.lower().startswith('ak-'):
        return None

    core_raw = stem[3:]              # preserve original case, strip 'ak-'
    core     = core_raw.lower()      # lowercase for all matching

    # Strip version suffix (-v1, -v2, -v3)
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version  = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core     = core[:vm.start()]

    # Strip '-large-plate' / '-large' quality/format indicator
    for strip_suf in ('-large-plate', '-large'):
        if core.endswith(strip_suf):
            core_raw = core_raw[:-len(strip_suf)]
            core     = core[:-len(strip_suf)]
            break

    # Vehicle class
    if subfolder == 'ak-non-passenger':
        vehicle_class = 'Other'
    elif 'motorcycle' in core:
        vehicle_class = 'Motorcycle'
    else:
        vehicle_class = 'Passenger'

    # Series + category routing
    subcat = AK_SUBFOLDER_CATEGORIES.get(subfolder)
    if subcat is not None:
        # ak-schools, ak-veteran: direct category, Specialty series
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']
        series = AK_SPECIALTY_SERIES

    elif subfolder == 'ak-standard-issue':
        series = AK_STD_ISSUE_SERIES
        cat_id, cat_conf = AK_STD_ISSUE_DEFAULT
        for keywords, cid, conf in AK_STD_ISSUE_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    elif subfolder == 'ak-non-passenger':
        series = AK_SPECIALTY_SERIES
        cat_id, cat_conf = AK_NON_PASSENGER_DEFAULT
        for keywords, cid, conf in AK_NON_PASSENGER_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    else:  # ak-specialty (and any unexpected subfolder)
        series = AK_SPECIALTY_SERIES
        cat_id, cat_conf = AK_SPECIALTY_DEFAULT
        for keywords, cid, conf in AK_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text  = to_title(core_raw)
    plate_name = f'AK - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── AZ parser ─────────────────────────────────────────────────────────────────
def parse_az(stem: str, subfolder: str, actual_filename: str):
    """Parse a single AZ (Arizona) plate image across 6 subfolders.

    Series routing:
      az-standard-issue  → classic/hot-rod → 1980 series (674)
                         → year match 2008/1996/1980 → 672/673/674
      az-non-passenger   → AZ_NP_SERIES (671), vehicle class Other
      all others         → AZ_SPECIALTY_SERIES (670)

    Filename normalisation:
      -blank            stripped from display (template/sample indicator)
      -motorcycle       stripped; Motorcycle class set
      Stripping is iterative: handles -motorcycle-blank and -blank-motorcycle

    Known skipped files:
      za-dealer-2014.jpg  — misnamed ('za-' prefix); will appear in skipped list
      as-navajo-nation-embossed.png  — misnamed ('as-' prefix); will appear in skipped list
      az-standard-issue-2008-amateur-radio exists as both .jpg and .png;
        slug deduplication appends '-2' to the second one
    """
    if not stem.lower().startswith('az-'):
        return None

    core_raw = stem[3:]                  # strip 'az-', preserve case
    core     = core_raw.lower()          # normalised for matching

    # Iteratively strip trailing -blank and -motorcycle (appear in either order)
    vehicle_class = 'Other' if subfolder == 'az-non-passenger' else 'Passenger'
    for _ in range(2):
        if core.endswith('-blank'):
            core     = core[:-6]
            core_raw = core_raw[:-6]
        if core.endswith('-motorcycle'):
            if subfolder != 'az-non-passenger':
                vehicle_class = 'Motorcycle'
            core     = core[:-11]
            core_raw = core_raw[:-11]

    # Version detection
    version = ''
    vm = re.search(r'-v(\d+)$', core)
    if vm:
        version  = f' V{vm.group(1)}'
        core_raw = core_raw[:vm.start()]
        core     = core[:vm.start()]

    # Series + category routing
    subcat = AZ_SUBFOLDER_CATEGORIES.get(subfolder)

    if subcat is not None:
        # az-veteran, az-schools, az-sports, az-outdoors
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']
        series           = AZ_SPECIALTY_SERIES

    elif subfolder == 'az-non-passenger':
        series = AZ_NP_SERIES
        cat_id, cat_conf = AZ_NON_PASSENGER_DEFAULT
        for keywords, cid, conf in AZ_NON_PASSENGER_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    elif subfolder == 'az-standard-issue':
        # Classic/hot-rod always go to 1980 series regardless of year in filename
        if any(kw in core for kw in AZ_CLASSIC_KEYWORDS):
            series   = AZ_STD_ISSUE_SERIES['1980']
            cat_id, cat_conf = CAT['Standard Issue'], 95
        else:
            # Year-based routing; also handles pre-1980 dates (197x → 1980 series)
            year_m = re.search(r'(2008|1996|1980)', core)
            if year_m:
                series = AZ_STD_ISSUE_SERIES[year_m.group(1)]
            elif re.search(r'197\d', core):
                series = AZ_STD_ISSUE_SERIES['1980']
            else:
                series = AZ_STD_ISSUE_DEFAULT
            cat_id, cat_conf = AZ_STD_ISSUE_CAT_DEFAULT
            for keywords, cid, conf in AZ_STD_ISSUE_CAT_RULES:
                if any(kw in core for kw in keywords):
                    cat_id, cat_conf = cid, conf
                    break

    else:  # az-specialty (and any unexpected subfolder)
        series = AZ_SPECIALTY_SERIES
        cat_id, cat_conf = AZ_SPECIALTY_DEFAULT
        for keywords, cid, conf in AZ_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text  = to_title(core_raw)
    plate_name = f'AZ - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── AL parser ─────────────────────────────────────────────────────────────────
def parse_al(stem: str, subfolder: str, actual_filename: str):
    """Parse a single AL (Alabama) plate image across 7 subfolders.

    Series routing:
      al-standard-issue → year-matched series (659–662)
      all other subfolders → AL_SPECIALTY_SERIES (663)

    Vehicle class:
      'motorcycle' in filename → Motorcycle
      al-non-passenger subfolder → Other
      default → Passenger
    """
    if not stem.lower().startswith('al-'):
        return None

    core_raw = stem[3:]          # preserve original case, strip 'al-'
    core     = core_raw.lower()  # lowercase for all matching

    # Vehicle class (motorcycle wins over non-passenger Other default)
    if 'motorcycle' in core:
        vehicle_class = 'Motorcycle'
    elif subfolder == 'al-non-passenger':
        vehicle_class = 'Other'
    else:
        vehicle_class = 'Passenger'

    # Series + category routing by subfolder
    subcat = AL_SUBFOLDER_CATEGORIES.get(subfolder)

    if subcat is not None:
        # al-fraternal, al-outdoor, al-schools, al-veteran
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']
        series           = AL_SPECIALTY_SERIES
        display_core     = core_raw

    elif subfolder == 'al-standard-issue':
        # Strip leading 'standard-' from display name if present
        if core.startswith('standard-'):
            display_core = core_raw[len('standard-'):]
            core_match   = core[len('standard-'):]
        else:
            display_core = core_raw
            core_match   = core
        # Year-based series selection
        series = AL_STD_ISSUE_DEFAULT
        for year, ser in AL_STD_ISSUE_SERIES.items():
            if year in core_match:
                series = ser
                break
        # Category override for vintage/antique within standard-issue subfolder
        if 'vintage' in core or 'antique' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif subfolder == 'al-non-passenger':
        series       = AL_SPECIALTY_SERIES
        display_core = core_raw
        cat_id, cat_conf = AL_NON_PASSENGER_DEFAULT
        for keywords, cid, conf in AL_NON_PASSENGER_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    else:  # al-specialty (and any unexpected subfolder)
        series       = AL_SPECIALTY_SERIES
        display_core = core_raw
        cat_id, cat_conf = AL_SPECIALTY_DEFAULT
        for keywords, cid, conf in AL_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text  = to_title(display_core)
    plate_name = f'AL - {name_text}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── AR parser ─────────────────────────────────────────────────────────────────
def parse_ar(stem: str, subfolder: str, actual_filename: str):
    """Parse a single AR (Arkansas) plate image across 8 subfolders.

    Series routing:
      ar-non-passenger       → AR_NP_SERIES (668), vehicle class Other
      ar-standard-issue      → year-matched series (664–667), category overrides
      all other subfolders   → AR_SPECIALTY_SERIES (669)

    Vehicle class:
      ar-non-passenger       → Other
      'motorcycle' in name   → Motorcycle
      default                → Passenger

    Filename normalisation:
      - Underscores → hyphens for matching and display
      - '-license-plate' suffix (and variants) stripped
      - '-design-N' / '-Nth-design' → version suffix V1/V2
      - Quality tags (_lg, _sm, _small, _large) stripped
    """
    if not stem.lower().startswith('ar-'):
        return None

    core_raw = stem[3:]                              # strip 'ar-', preserve case
    core     = core_raw.lower().replace('_', '-')    # normalised for matching
    core_d   = core_raw.replace('_', '-')            # normalised for display

    # Strip image quality/size suffixes (-lg, -sm, -small, -large)
    for suf in ('-lg', '-sm', '-small', '-large'):
        if core.endswith(suf):
            core   = core[:-len(suf)]
            core_d = core_d[:-len(suf)]
            break

    # Version detection: '-license-plate-design-N' or '-license-plate-Nth-design', then '-vN'
    version = ''
    vm = re.search(r'-license-plate-design-(\d+)$', core)
    if not vm:
        vm = re.search(r'-license-plate-(\d+)(?:st|nd|rd|th)-design$', core)
    if vm:
        version = f' V{vm.group(1)}'
        core    = core[:vm.start()]
        core_d  = core_d[:vm.start()]
    else:
        vm = re.search(r'-v(\d+)$', core)
        if vm:
            version = f' V{vm.group(1)}'
            core    = core[:vm.start()]
            core_d  = core_d[:vm.start()]

    # Strip remaining '-license-plate' and common trailing qualifiers
    for pat in (r'-license-plate-new-design$', r'-license-plate-current$',
                r'-license-plate-free$',        r'-license-plate$'):
        m = re.search(pat, core)
        if m:
            core   = core[:m.start()]
            core_d = core_d[:m.start()]
            break

    # Vehicle class (motorcycle suffix removed from display core)
    if subfolder == 'ar-non-passenger':
        vehicle_class = 'Other'
    elif 'motorcycle' in core:
        vehicle_class = 'Motorcycle'
        core   = re.sub(r'-motorcycle$', '', core)
        core_d = re.sub(r'(?i)-motorcycle$', '', core_d)
    else:
        vehicle_class = 'Passenger'

    # Series + category routing
    subcat = AR_SUBFOLDER_CATEGORIES.get(subfolder)

    if subcat is not None:
        # ar-fraternal, ar-outdoors, ar-schools, ar-sports, ar-veteran
        cat_id, cat_conf = subcat['cat_id'], subcat['conf']
        series           = AR_SPECIALTY_SERIES

    elif subfolder == 'ar-standard-issue':
        # Year-based series: find FIRST matching year in filename (handles '1978-1988' → 1978)
        year_m = re.search(r'(2006|1996|1988|1978)', core)
        series = AR_STD_ISSUE_SERIES[year_m.group(1)] if year_m else AR_STD_ISSUE_DEFAULT
        cat_id, cat_conf = AR_STD_ISSUE_CAT_DEFAULT
        for keywords, cid, conf in AR_STD_ISSUE_CAT_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    elif subfolder == 'ar-non-passenger':
        series = AR_NP_SERIES
        cat_id, cat_conf = AR_NON_PASSENGER_DEFAULT
        for keywords, cid, conf in AR_NON_PASSENGER_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    else:  # ar-specialty (and any unexpected subfolder)
        series = AR_SPECIALTY_SERIES
        cat_id, cat_conf = AR_SPECIALTY_DEFAULT
        for keywords, cid, conf in AR_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    name_text  = to_title(core_d)
    plate_name = f'AR - {name_text}{version}'

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── AB parser ─────────────────────────────────────────────────────────────────
def parse_ab(stem: str) -> dict:
    """Parse a single AB (Alberta) plate image.

    AB is a flat folder (no subfolders). All files are .jpg.
    Routing:
      - 'standard-issue' in filename  OR  bare 'motorcycle' filename
          → AB_STD_ISSUE_SERIES (655), Standard Issue category
      - everything else → AB_SPECIALTY_SERIES (656), keyword-derived category

    Filename quirks handled:
      - Underscores (e.g. calgary_flames) normalized to hyphens for matching + display
      - '-small' / '_small' quality indicator stripped from name
    """
    if not stem.lower().startswith('ab-'):
        return None

    raw  = stem[3:]                             # preserve original case, strip 'ab-'
    core = raw.lower().replace('_', '-')        # lowercase + uniform separators

    # Strip '-small' / '_small' quality indicator (may appear before a year suffix)
    core = re.sub(r'[_-]small', '', core)
    raw  = re.sub(r'(?i)[_-]small', '', raw)

    # Vehicle class
    # 'ab-motorcycle' is the bare standard-issue motorcycle plate
    vehicle_class = 'Motorcycle' if core == 'motorcycle' else 'Passenger'

    # Series + category routing
    if 'standard-issue' in core or core == 'motorcycle':
        series   = AB_STD_ISSUE_SERIES
        cat_id   = CAT['Standard Issue']
        cat_conf = 95
    else:
        series   = AB_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 72   # default
        for keywords, cid, conf in AB_SPECIALTY_RULES:
            if any(kw in core for kw in keywords):
                cat_id, cat_conf = cid, conf
                break

    # Build display name (underscores → hyphens for to_title)
    name_text  = to_title(raw.replace('_', '-'))
    plate_name = f'AB - {name_text}'

    return {
        'filename':      stem + '.jpg',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id if cat_conf >= 70 else None,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'notes':         [],
        'src_subfolder': '',
    }


# ── OH parser ─────────────────────────────────────────────────────────────────
def parse_oh(stem: str, subfolder: str, actual_filename: str):
    """Parse a single OH (Ohio) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      oh-standard-issue              → year-routed: 2013→802, 2008→803;
                                       all others (2021 + passenger variants) → 801
      oh-non-passenger and government→ OH_NP_SERIES (805)
      all others                     → OH_SPECIALTY_SERIES (804)

    Vehicle class:
      -motorcycle suffix             → Motorcycle
      non-passenger: camp/farm/transit-bus, livery-vehicle → Commercial
      all others                     → Passenger
    """
    if not stem.lower().startswith('oh-'):
        return None

    core_raw = stem[3:]        # strip 'oh-'
    core     = core_raw.lower()

    # ── Vehicle class / suffix detection ─────────────────────────────────────
    vehicle_class = 'Passenger'
    mc_suffix     = ''
    if core.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        mc_suffix     = ' - Motorcycle'
        core_raw = core_raw[:-11]
        core     = core[:-11]

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue
        'standard-issue-2021':                                       'Standard Issue - 2021 - Sunrise',
        'standard-issue-2013-pride':                                 'Standard Issue - 2013 - Pride',
        'standard-issue-2008-beautiful':                             'Standard Issue - 2008 - Beautiful',
        # First responder
        'ohio-cops':                                                 'Ohio COPS',
        # Fraternal
        'fraternal-order-of-police-associate':                       'Fraternal Order of Police - Associate',
        'sigma-gamma-rho-emblem':                                    'Sigma Gamma Rho - Emblem',
        'sigma-gamma-rho-shield':                                    'Sigma Gamma Rho - Shield',
        # Military / Veteran — filename typos
        'marine-corps-vietname-veteran':                              'Marine Corps Vietnam Veteran',
        'conbat-infantryman-badge-no-star':                          'Combat Infantryman Badge - No Star',
        'conbat-infantryman-badge-one-star':                         'Combat Infantryman Badge - One Star',
        'conbat-infantryman-badge-two-star':                         'Combat Infantryman Badge - Two Star',
        # Military / Veteran — formatting
        'army-us-armed-forces-active-duty':                          'Army - US Armed Forces - Active Duty',
        'army-us-armed-forces-reserve':                              'Army - US Armed Forces - Reserve',
        'army-us-armed-forces-retired':                              'Army - US Armed Forces - Retired',
        'army-us-armed-forces-veteran':                              'Army - US Armed Forces - Veteran',
        'bronze-star-combat-veteran':                                'Bronze Star - Combat Veteran',
        'coast-guard-combat-action-ribbon-combat-veteran':           'Coast Guard Combat Action Ribbon - Combat Veteran',
        'combat-action-badge-combat-veteran':                        'Combat Action Badge - Combat Veteran',
        'combat-action-ribbon-combat-veteran':                       'Combat Action Ribbon - Combat Veteran',
        'combat-medical-badge-combat-veteran':                       'Combat Medical Badge - Combat Veteran',
        "dav-keeping-our-promise-to-america's-veterans":             "DAV - Keeping Our Promise to America's Veterans",
        'expeditionary-force-star-veteran':                          'Expeditionary Force Star - Veteran',
        'freedom-is-not-free-folds-of-honor':                        'Freedom Is Not Free - Folds of Honor',
        'global-war-on-terrorism-afghanistan-medal':                 'Global War on Terrorism - Afghanistan Medal',
        'global-war-on-terrorism-expeditionary-medal':               'Global War on Terrorism - Expeditionary Medal',
        'global-war-on-terrorism-iraq-medal':                        'Global War on Terrorism - Iraq Medal',
        'global-war-on-terrorism-service-medal':                     'Global War on Terrorism - Service Medal',
        'gold-star-family-vietnam':                                  'Gold Star Family - Vietnam',
        'korea-us-flag-veteran':                                     'Korea - US Flag - Veteran',
        'kosovo-medal-veteran':                                      'Kosovo Medal - Veteran',
        'ohio-air-national-guard-retired':                           'Ohio Air National Guard - Retired',
        'ohio-army-national-guard-retired':                          'Ohio Army National Guard - Retired',
        'persian-gulf-star-veteran':                                 'Persian Gulf Star - Veteran',
        'pow-mia':                                                   'POW / MIA',
        'prisoner-of-war-veteran':                                   'Prisoner of War - Veteran',
        'purple-heart-combat-wounded':                               'Purple Heart - Combat Wounded',
        'purple-heart-combat-wounded-disabled':                      'Purple Heart - Combat Wounded - Disabled',
        'silver-star-combat-veteran':                                'Silver Star - Combat Veteran',
        'us-armed-forces-active-duty-space-force':                   'US Armed Forces - Active Duty - Space Force',
        'us-army-aviation-active-duty':                              'US Army Aviation - Active Duty',
        'us-army-aviation-retired':                                  'US Army Aviation - Retired',
        'us-army-aviation-veteran':                                  'US Army Aviation - Veteran',
        'us-paratrooper':                                            'US Paratrooper',
        'us-uniformed-services-active-duty-noaa':                    'US Uniformed Services - Active Duty - NOAA',
        'us-uniformed-services-active-duty-usphs':                   'US Uniformed Services - Active Duty - USPHS',
        'vietnam-star-veteran':                                      'Vietnam Star - Veteran',
        'vietnam-veteran-flag':                                      'Vietnam Veteran - Flag',
        'voiture-40-et-8':                                           'Voiture 40 et 8',
        'women-veterans-us-armed-forces-retired-air-force':          'Women Veterans - US Armed Forces - Retired - Air Force',
        'women-veterans-us-armed-forces-veteran-air-force':          'Women Veterans - US Armed Forces - Veteran - Air Force',
        'women-veterans-us-uniformed services-veteran-noaa':         'Women Veterans - US Uniformed Services - Veteran - NOAA',
        'women-veterans-us-us-uniformed-services-usphs':             'Women Veterans - US Uniformed Services - USPHS',
        'world-war-ii-veteran':                                      'World War II Veteran',
        # Outdoors
        'erie-our-great-lake':                                       'Erie - Our Great Lake',
        'natures-preserve':                                          "Nature's Preserve",
        'scenic-rivers-heron':                                       'Scenic Rivers - Heron',
        'support-wildlfe-bald-eagle':                                'Support Wildlife - Bald Eagle',
        'trees4ohio':                                                'Trees 4 Ohio',
        'wildlife-northern-cardinal':                                'Wildlife - Northern Cardinal',
        # Schools
        'archbishop-moeller-high-school-crusaders':                  'Archbishop Moeller High School - Crusaders',
        'canton-mckinley-bulldogs':                                  'Canton McKinley Bulldogs',
        'st-charles-academy':                                        'St. Charles Academy',
        'univesity-of-mount-union':                                  'University of Mount Union',
        'unversity-school':                                          'University School',
        # Specialty — typos / URL filenames / formatting
        'a-kid-again-where-illness-stops-and-adventure-begins':      'A Kid Again - Where Illness Stops and Adventure Begins',
        'autismohio.org':                                            'Autism Ohio',
        'bully-free-car':                                            'Bully-Free Car',
        'carpenters-union-proud-union-member':                       'Carpenters Union - Proud Union Member',
        'celebrate-kids-casa':                                       'Celebrate Kids CASA',
        'choos-life':                                                'Choose Life',
        'coal-keeps-the-lights-on-friends-of-coal':                  'Coal Keeps the Lights On - Friends of Coal',
        'defeat-als-ohioals.org':                                    'Defeat ALS',
        'downssyndromeohio.org':                                     'Down Syndrome Ohio',
        'enddipg.org':                                               'End DIPG',
        'essential-ohio-energy+':                                    'Essential Ohio Energy+',
        'ffa-agricultural-education':                                'FFA - Agricultural Education',
        'ffa-truck':                                                 'FFA - Truck',
        'girls-on-the-run-learn-dream-live-run':                     'Girls on the Run - Learn, Dream, Live, Run',
        'honor-our-fallen.us':                                       'Honor Our Fallen',
        'hope-prayersfrommaria.org':                                 'Hope - Prayers From Maria',
        'nationwide-childrens-hospital':                             "Nationwide Children's Hospital",
        'ohio4h-head-heart-hands-health':                            'Ohio 4-H - Head, Heart, Hands, Health',
        'ohio-beef-truck':                                           'Ohio Beef - Truck',
        'ohio-pupil-transportation-safety-first':                    'Ohio Pupil Transportation - Safety First',
        'ohioshorses.com':                                           'Ohio Horses',
        'post-traumatic-stress-awareness':                           'Post-Traumatic Stress Awareness',
        'ronald-mcdonald-house':                                     'Ronald McDonald House',
        'st-baldricks.org-conquer-childhood-cancers':                "St. Baldrick's Foundation - Conquer Childhood Cancers",
        'the-nra-foundation':                                        'The NRA Foundation',
        'www.bottomsup.life':                                        'Bottoms Up',
    }

    name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name = f'OH - {name_text}{mc_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'oh-standard-issue':
        if '2013' in core:
            series = OH_STD_2013_SERIES
        elif '2008' in core:
            series = OH_STD_2008_SERIES
        else:
            series = OH_STD_2021_SERIES
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'disability' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif any(x in core for x in ('historical-vehicle', 'street-rod', 'collector')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif 'non-passenger' in sub:
        series = OH_NP_SERIES
        if any(x in core for x in ('camp-bus', 'transit-bus', 'farm-bus', 'livery-vehicle')):
            vehicle_class = 'Commercial'
        cat_id   = CAT['Agricultural'] if 'farm-bus' in core else CAT['Other / Specialty']
        cat_conf = 88 if 'farm-bus' in core else 80

    elif sub == 'oh-military-veteran':
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif sub == 'oh-first-responder':
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'oh-fraternal':
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 95

    elif sub == 'oh-outdoors':
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 92

    elif sub == 'oh-schools':
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif sub == 'oh-sports':
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 95

    elif sub == 'oh-specialty':
        series = OH_SPECIALTY_SERIES
        if any(x in core for x in ('cancer', 'autism', 'syndrome', 'hospital',
                                    'organ-donor', 'red-cross', 'traumatic-stress',
                                    'als', 'enddipg', 'prayersfrom', 'kid-again',
                                    'diabetes', 'ovarian', 'pancreatic', 'prostate',
                                    'triple-negative', 'mcdonald-house')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif any(x in core for x in ('ohio4h', 'ffa', 'ohio-beef', 'agricultural')):
            cat_id, cat_conf = CAT['Agricultural'], 90
        elif any(x in core for x in ('lincoln-highway', 'fallen-timbers', 'stan-hywet',
                                      'commodore', 'statehouse', 'preserve-ohio',
                                      "perry's", 'hall-of-fame', 'circleville')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif any(x in core for x in ('scouts', 'carpenters-union', 'east-europeans',
                                      'realtors', 'celebrate-kids', 'united-states-power')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        elif 'ohio-zoo' in core:
            cat_id, cat_conf = CAT['Conservation / Environment'], 90
        elif 'superman' in core:
            cat_id, cat_conf = CAT['Arts / Culture'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    else:
        series           = OH_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     36,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── OK parser ─────────────────────────────────────────────────────────────────
def parse_ok(stem: str, subfolder: str, actual_filename: str):
    """Parse a single OK (Oklahoma) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      ok-standard-issue              → year-routed: 2017→807; all others→806
      ok-non-passenger-government    → OK_NP_SERIES (810)
      ok-military-veteran            → OK_MIL_SERIES (809)
      all others                     → OK_SPECIALTY_SERIES (808)

    Vehicle class:
      -motorcycle suffix             → Motorcycle
      non-passenger commercial/trailer → Commercial / Trailer
      chickasaw/choctaw motorcycle variants → Motorcycle
      all others                     → Passenger
    """
    if not stem.lower().startswith('ok-'):
        return None

    core_raw = stem[3:]        # strip 'ok-'
    core     = core_raw.lower()

    # ── Vehicle class / suffix detection ─────────────────────────────────────
    vehicle_class = 'Passenger'
    mc_suffix     = ''
    if core.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        mc_suffix     = ' - Motorcycle'
        core_raw = core_raw[:-11]
        core     = core[:-11]

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue
        'standard-issue-2024-soviet':                               'Standard Issue - 2024 - Imagine That',
        'standard-issue-2017-scissortail':                          'Standard Issue - 2017 - Scissortail',
        # Standard issue variants
        'amateur-radio-back':                                       'Amateur Radio - Back',
        'amateur-radio-front':                                      'Amateur Radio - Front',
        'personalized-blue':                                        'Personalized - Blue',
        'personalized-gray':                                        'Personalized - Gray',
        'personalized-pink':                                        'Personalized - Pink',
        'personalized-tan':                                         'Personalized - Tan',
        'personalized-white':                                       'Personalized - White',
        'personalized-yellow':                                      'Personalized - Yellow',
        'physically-disabled-back':                                 'Physically Disabled - Back',
        'physically-disabled-front':                                'Physically Disabled - Front',
        # First responder
        'highway-patrol-retired':                                   'Highway Patrol - Retired',
        # Fraternal
        'zeta-phi-beta-phi-beta-sigma':                             'Zeta Phi Beta / Phi Beta Sigma',
        # Military / Veteran
        'd-day-survivor':                                           'D-Day Survivor',
        'multi-decoration-personalized-1':                          'Multi-Decoration - Personalized 1',
        'multi-decoration-personalized-2':                          'Multi-Decoration - Personalized 2',
        'multi-decoration-prenumbered':                             'Multi-Decoration - Pre-Numbered',
        'oklahoma-womens-veteran':                                  "Oklahoma Women's Veteran",
        'usn-seabees-civil-engineer-corps':                         'USN Seabees - Civil Engineer Corps',
        'combat-action-us-marines':                                 'Combat Action - US Marines',
        'combat-action-us-navy':                                    'Combat Action - US Navy',
        'distinguished-service-medal-army':                         'Distinguished Service Medal - Army',
        'distinguished-service-medal-coast-guard':                  'Distinguished Service Medal - Coast Guard',
        'distinguished-service-medal-navy':                         'Distinguished Service Medal - Navy',
        'distinguished-service-medal-usmc':                         'Distinguished Service Medal - USMC',
        'korean-war-veteran-45th-infantry':                         'Korean War Veteran - 45th Infantry',
        'korean-war-veteran-army':                                  'Korean War Veteran - Army',
        'korean-war-veteran-coast-guard':                           'Korean War Veteran - Coast Guard',
        'korean-war-veteran-navy':                                  'Korean War Veteran - Navy',
        'korean-war-veteran-usaf':                                  'Korean War Veteran - USAF',
        'korean-war-veteran-usmc':                                  'Korean War Veteran - USMC',
        'united-states-air-force-reserve':                          'United States Air Force - Reserve',
        'united-states-air-force-retired':                          'United States Air Force - Retired',
        'united-states-army-reserve':                               'United States Army - Reserve',
        'united-states-army-retired':                               'United States Army - Retired',
        'united-states-coast-guard-reserve':                        'United States Coast Guard - Reserve',
        'united-states-coast-guard-retired':                        'United States Coast Guard - Retired',
        'united-states-marines-reserve':                            'United States Marines - Reserve',
        'united-states-marines-retired':                            'United States Marines - Retired',
        'united-states-navy-reserve':                               'United States Navy - Reserve',
        'united-states-navy-retired':                               'United States Navy - Retired',
        'veterans-of-the-united-states-armed-forces-air-force':     'Veterans of the United States Armed Forces - Air Force',
        'veterans-of-the-united-states-armed-forces-army':          'Veterans of the United States Armed Forces - Army',
        'veterans-of-the-united-states-armed-forces-coast-guard':   'Veterans of the United States Armed Forces - Coast Guard',
        'veterans-of-the-united-states-armed-forces-marines':       'Veterans of the United States Armed Forces - Marines',
        'veterans-of-the-united-states-armed-forces-navy':          'Veterans of the United States Armed Forces - Navy',
        'world-war-ii-veteran-45th-infantry':                       'World War II Veteran - 45th Infantry',
        'world-war-ii-veteran-army':                                'World War II Veteran - Army',
        'world-war-ii-veteran-navy':                                'World War II Veteran - Navy',
        'world-war-ii-veteran-usaf':                                'World War II Veteran - USAF',
        'world-war-ii-veteran-uscg':                                'World War II Veteran - USCG',
        'world-war-ii-veteran-usmc':                                'World War II Veteran - USMC',
        # Non-passenger
        'apportioned-2021':                                         'Apportioned - 2021',
        'non-expiring-trailer':                                     'Non-Expiring Trailer',
        # Outdoors
        'environmental-awareness-bison':                            'Environmental Awareness - Bison',
        'environmental-awareness-oklahoma-fields':                  'Environmental Awareness - Oklahoma Fields',
        'state-parks-supporter-pavilion':                           'State Parks Supporter - Pavilion',
        'state-parks-supporter-rv':                                 'State Parks Supporter - RV',
        'wildlife-conservation-bass':                               'Wildlife Conservation - Bass',
        'wildlife-conservation-deer':                               'Wildlife Conservation - Deer',
        'wildlife-conservation-mallard':                            'Wildlife Conservation - Mallard',
        'wildlife-conservation-quail':                              'Wildlife Conservation - Quail',
        'wildlife-conservation-scissor-tail':                       'Wildlife Conservation - Scissor-Tail',
        'wildlife-conservation-striper':                            'Wildlife Conservation - Striper',
        'wildlife-conservation-texas-horned-lizard':                'Wildlife Conservation - Texas Horned Lizard',
        'wildlife-conservation-trout':                              'Wildlife Conservation - Trout',
        'wildlife-conservation-turkey':                             'Wildlife Conservation - Turkey',
        # Schools
        'northeastern-oklahoma-a-m-college':                        'Northeastern Oklahoma A&M College',
        'k-state':                                                  'K-State',
        'okc-central-high-school':                                  'OKC Central High School',
        # Specialty
        'abate-of-oklahoma':                                        'ABATE of Oklahoma',
        'ambucs':                                                   'AMBUCS',
        'chickasaw-nation-motorcycle-personalized':                  'Chickasaw Nation - Motorcycle - Personalized',
        'chickasaw-nation-personalized':                            'Chickasaw Nation - Personalized',
        'chickasaw-nation-physically-disabled':                     'Chickasaw Nation - Physically Disabled',
        'chickasaw-nation-physically-disabled-front':               'Chickasaw Nation - Physically Disabled - Front',
        'choctaw-nation-motorcycle-personalized':                    'Choctaw Nation - Motorcycle - Personalized',
        'choctaw-nation-personalized':                              'Choctaw Nation - Personalized',
        'choctaw-nation-physically-disabled-1':                     'Choctaw Nation - Physically Disabled - 1',
        'choctaw-nation-physically-disabled-2':                     'Choctaw Nation - Physically Disabled - 2',
        'choctaw-nation-physically-disabled-3':                     'Choctaw Nation - Physically Disabled - 3',
        'don-t-tread-on-me':                                        "Don't Tread on Me",
        'fight-breast-cancer-black':                                'Fight Breast Cancer - Black',
        'fight-breast-cancer-pink':                                 'Fight Breast Cancer - Pink',
        'four-h':                                                   '4-H',
        'historic-route-66':                                        'Historic Route 66',
        'naacp':                                                    'NAACP',
        'ninety-nines':                                             'Ninety-Nines',
        'oklahoma-city-bombing-victims-and-survivors':              'Oklahoma City Bombing - Victims and Survivors',
        # Sports
        'bike-oklahoma-oklahoma-bicycling-coalition':               'Bike Oklahoma - Oklahoma Bicycling Coalition',
        'nascar':                                                   'NASCAR',
        'nascar-carl-edwards':                                      'NASCAR - Carl Edwards',
        'nascar-dale-earnhardt':                                    'NASCAR - Dale Earnhardt',
        'nascar-dale-earnhardt-hall-of-fame':                       'NASCAR - Dale Earnhardt Hall of Fame',
        'nascar-dale-earnhardt-jr':                                 'NASCAR - Dale Earnhardt Jr.',
        'nascar-david-ragan':                                       'NASCAR - David Ragan',
        'nascar-denny-hamlin':                                      'NASCAR - Denny Hamlin',
        'nascar-greg-biffle':                                       'NASCAR - Greg Biffle',
        'nascar-jeff-burton':                                       'NASCAR - Jeff Burton',
        'nascar-jeff-gordon':                                       'NASCAR - Jeff Gordon',
        'nascar-jimmie-johnson':                                    'NASCAR - Jimmie Johnson',
        'nascar-joey-logano':                                       'NASCAR - Joey Logano',
        'nascar-juan-pablo-montoya':                                'NASCAR - Juan Pablo Montoya',
        'nascar-kevin-harvick':                                     'NASCAR - Kevin Harvick',
        'nascar-kyle-busch':                                        'NASCAR - Kyle Busch',
        'nascar-mark-martin':                                       'NASCAR - Mark Martin',
        'nascar-matt-kenseth':                                      'NASCAR - Matt Kenseth',
        'nascar-richard-petty-historic':                            'NASCAR - Richard Petty Historic',
        'nascar-ryan-newman':                                       'NASCAR - Ryan Newman',
        'nascar-tony-stewart':                                      'NASCAR - Tony Stewart',
        'state-parks-supporter-golf':                               'State Parks Supporter - Golf',
        'u-s-olympics':                                             'U.S. Olympics',
    }

    name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name = f'OK - {name_text}{mc_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'ok-standard-issue':
        series = OK_STD_2017_SERIES if '2017' in core else OK_STD_2024_SERIES
        if 'amateur-radio' in core:
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'physically-disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        elif 'antique-or-classic' in core:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif 'personalized' in core:
            cat_id, cat_conf = CAT['Other / Specialty'], 85
        else:
            cat_id, cat_conf = CAT['Standard Issue'], 95

    elif sub == 'ok-non-passenger-government':
        series = OK_NP_SERIES
        if any(x in core for x in ('commercial-truck', 'apportioned')):
            vehicle_class = 'Commercial'
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        elif 'non-expiring-trailer' in core:
            vehicle_class = 'Trailer'
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        else:
            cat_id, cat_conf = CAT['Government / Exempt'], 90

    elif sub == 'ok-military-veteran':
        series           = OK_MIL_SERIES
        cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif sub == 'ok-first-responder':
        series           = OK_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'ok-fraternal':
        series           = OK_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 95

    elif sub == 'ok-outdoors':
        series           = OK_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 92

    elif sub == 'ok-schools':
        series           = OK_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif sub == 'ok-sports':
        series           = OK_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 95

    elif sub == 'ok-specialty':
        series = OK_SPECIALTY_SERIES
        # Tribal motorcycle variants need Motorcycle class
        if any(x in core for x in ('chickasaw-nation-motorcycle', 'choctaw-nation-motorcycle')):
            vehicle_class = 'Motorcycle'
        if any(x in core for x in ('cancer', 'autism', 'sclerosis', 'march-of-dimes',
                                    'child-abuse', 'organ-eye', 'blood-institute',
                                    'crime-victim', 'safe-kids')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif 'physically-disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif any(x in core for x in ('quarter-horse', 'future-farmers', 'four-h',
                                      'agricultural')):
            cat_id, cat_conf = CAT['Agricultural'], 90
        elif any(x in core for x in ('statehood-centennial', 'oklahoma-history',
                                      'route-66', 'greenwood', 'bombing', 'tulsa-flag')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88
        elif any(x in core for x in ('folds-of-honor', 'support-our-troops',
                                      'sons-of-the-american-revolution')):
            cat_id, cat_conf = CAT['Military / Veteran'], 88
        elif any(x in core for x in ('naacp', 'scouts', 'jaycees', 'realtors',
                                      'red-cross', 'ambucs', 'accountant',
                                      'national-rifle', 'downed-bikers', 'abate',
                                      'mustang-club', 'red-dirt-jeeps', 'ninety-nines')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        elif any(x in core for x in ('tulsa-zoo', 'animal-friendly')):
            cat_id, cat_conf = CAT['Conservation / Environment'], 88
        elif 'square-and-round' in core:
            cat_id, cat_conf = CAT['Arts / Culture'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    else:
        series           = OK_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     37,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── ON parser ─────────────────────────────────────────────────────────────────
def parse_on(stem: str, subfolder: str, actual_filename: str):
    """Parse a single ON (Ontario) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      on-standard-issue              → ON_STD_SERIES (811) — English + French variants
      all others                     → ON_SPECIALTY_SERIES (812)

    Vehicle class:
      -motorcycle suffix             → Motorcycle
      all others                     → Passenger

    Categories by subfolder:
      on-standard-issue              → Standard Issue (95%)
      on-government                  → Government / Exempt (90%)
      on-heritage                    → Historical / Commemorative (90%)
                                       EXCEPT veteran* → Military / Veteran (95%)
      on-novelty                     → Other / Specialty (80%)
      on-first-responder             → First Responder (95%)
      on-charity                     → Health & Awareness (90%)
      on-community-organizations     → Fraternal / Civic (85%)
                                       EXCEPT support-our-troops → Military / Veteran (90%)
      on-environment                 → Conservation / Environment (95%)
      on-outdoors                    → Conservation / Environment (88%)
      on-schools                     → School (95%)
      on-sports                      → Sports Team (90%)
    """
    if not stem.lower().startswith('on-'):
        return None

    core_raw = stem[3:]        # strip 'on-'
    core     = core_raw.lower()

    # ── Vehicle class / suffix detection ─────────────────────────────────────
    vehicle_class = 'Passenger'
    mc_suffix     = ''
    if core.endswith('-motorcycle'):
        vehicle_class = 'Motorcycle'
        mc_suffix     = ' - Motorcycle'
        core_raw = core_raw[:-11]
        core     = core[:-11]

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue
        'standard-issue-1995-yours-to-discover':        'Standard Issue - 1995 - Yours to Discover',
        'standard-issue-1995-tant-a-decouvrir':         'Standard Issue - 1995 - Tant \u00e0 D\u00e9couvrir',
        # Government
        'dont-drink-and-drive':                         "Don't Drink and Drive",
        # Heritage
        'franco-ontarian-flag':                         'Franco-Ontarian Flag',
        'garden-river-first-nation-ketegaunseebee':     'Garden River First Nation - Ketegaunseebee',
        'united-empire-loyalists-assn':                 'United Empire Loyalists Association',
        # First responder
        'paramedic-assn':                               'Paramedic Association',
        'professional-fire-fighters-assn':              'Professional Fire Fighters Association',
        # Charity
        'madd':                                         'MADD',
        'st-john-ambulance':                            'St. John Ambulance',
        # Community organizations
        'canadian-distillers-assn':                     'Canadian Distillers Association',
        'governor-generals-horse-guard-assn':           "Governor General's Horse Guard Association",
        'lincoln-and-welland-regiment-assn':            'Lincoln and Welland Regiment Association',
        'queens-own-rifles-of-canada':                  "Queen's Own Rifles of Canada",
        'queens-york-rangers':                          "Queen's York Rangers",
        # Outdoors
        'ottaway-valley-adventure-playground':          'Ottawa Valley Adventure Playground',
        # Schools
        'queens-university':                            "Queen's University",
        # Sports
        'hamilton-tiger-cats':                          'Hamilton Tiger-Cats',
        'intl-chang-hon-taekwon-do-federation':         'International Chang Hon Taekwon-Do Federation',
        'lacrosse-assn':                                'Lacrosse Association',
    }

    name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name = f'ON - {name_text}{mc_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'on-standard-issue':
        series           = ON_STD_SERIES
        cat_id, cat_conf = CAT['Standard Issue'], 95

    elif sub == 'on-government':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Government / Exempt'], 90

    elif sub == 'on-heritage':
        series = ON_SPECIALTY_SERIES
        if 'veteran' in core:
            cat_id, cat_conf = CAT['Military / Veteran'], 95
        else:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 90

    elif sub == 'on-novelty':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'on-first-responder':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'on-charity':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Health & Awareness'], 90

    elif sub == 'on-community-organizations':
        series = ON_SPECIALTY_SERIES
        if 'support-our-troops' in core:
            cat_id, cat_conf = CAT['Military / Veteran'], 90
        else:
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85

    elif sub == 'on-environment':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 95

    elif sub == 'on-outdoors':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 88

    elif sub == 'on-schools':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif sub == 'on-sports':
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:
        series           = ON_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     60,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── RI parser ─────────────────────────────────────────────────────────────────
def parse_ri(stem: str, subfolder: str, actual_filename: str):
    """Parse a single RI (Rhode Island) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      ri-standard-issue              → base-design-routed: sailboat→815, shark→816,
                                       all others (ocean, wave, electric-hybrid,
                                       antique, camper, etc.) → 814
      ri-non-passenger-government    → base-design-routed: sailboat→815, shark→816,
                                       all others → 814; farm/public-service/trailer → 817
      ri-military                    → RI_VET_SERIES (818)
      ri-first-responder             → RI_SPECIALTY_SERIES (817)
      ri-specialty                   → RI_SPECIALTY_SERIES (817)
      ri-outdoors                    → RI_SPECIALTY_SERIES (817)
      ri-school                      → RI_SPECIALTY_SERIES (817)
      ri-sports                      → RI_SPECIALTY_SERIES (817)

    Duplicate: ri-motorcycle-veteran → skip (duplicate of ri-veteran-motorcycle)
    Electric/Hybrid → always route to RI_STD_OCEAN_SERIES (814) per spec
    """
    if not stem.lower().startswith('ri-'):
        return None

    # Skip known duplicate
    if stem.lower() == 'ri-motorcycle-veteran':
        return None

    core_raw = stem[3:]        # strip 'ri-'
    core     = core_raw.lower()

    # ── Vehicle class detection ───────────────────────────────────────────────
    vehicle_class = 'Passenger'
    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
    elif (core.endswith('-commercial') or core.endswith('-commerical')
          or core.endswith('-combination') or core in ('commercial', 'combination', 'farm')):
        vehicle_class = 'Commercial'
    elif core == 'trailer':
        vehicle_class = 'Trailer'

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue base designs
        'standard-issue-ocean':                         'Standard Issue - 2023 - Ocean',
        'alternative-issue-sailboat':                   'Alternative Issue - 1992 - Sailboat',
        'alternative-issue-shark':                      'Alternative Issue - 2023 - Shark',
        'alternative-issue-shark-passenger':            'Alternative Issue - 2023 - Shark - Passenger',
        'alternative-issue-shark-motorcycle':           'Alternative Issue - 2023 - Shark - Motorcycle',
        'alternative-issue-wave':                       'Alternative Issue - Wave',
        # Electric/Hybrid variants
        'electric-hybrid':                              'Electric / Hybrid',
        'electric-hybrid-suburban':                     'Electric / Hybrid - Suburban',
        'electric-hybrid-combination':                  'Electric / Hybrid - Combination',
        'electric-hybrid-commercial':                   'Electric / Hybrid - Commercial',
        # Non-passenger base variants
        'alternative-issue-sailboat-commercial':        'Alternative Issue - Sailboat - Commercial',
        'alternative-issue-shark-combination':          'Alternative Issue - Shark - Combination',
        'alternative-issue-shark-commercial':           'Alternative Issue - Shark - Commercial',
        # Standard-issue class variants
        'custom-vehicle':                               'Custom Vehicle',
        'radio-operator':                               'Radio Operator',
        'street-rod':                                   'Street Rod',
        # Military
        'ex-pow':                                       'Ex-POW',
        'bronze-star-medal':                            'Bronze Star Medal',
        'disabled-veteran':                             'Disabled Veteran',
        'gold-star-family':                             'Gold Star Family',
        'national-guard':                               'National Guard',
        'purple-heart':                                 'Purple Heart',
        'veteran-motorcycle':                           'Veteran - Motorcycle',
        # First responder — typo fix and formatting
        'firefighter-commerical':                       'Firefighter - Commercial',
        'firefighter-combination':                      'Firefighter - Combination',
        'firefighter-old-design':                       'Firefighter - Old Design',
        # Specialty
        'autism-awareness':                             'Autism Awareness',
        'boy-scouts-of-america':                        'Boy Scouts of America',
        'bristol-fourth-of-july':                       'Bristol Fourth of July',
        'community-food-bank-mr-potato-head':           'Community Food Bank - Mr. Potato Head',
        'day-of-portugal':                              'Day of Portugal',
        'gaspee-days-committee':                        'Gaspee Days Committee',
        'gloria-gemma-breast-cancer-resource-foundation': 'Gloria Gemma Breast Cancer Resource Foundation',
        'knock-out-childhood-cancer':                   'Knock Out Childhood Cancer',
        # Outdoors
        'beavertail-lighthouse':                        'Beavertail Lighthouse',
        'commercial-fisheries-research-foundation':     'Commercial Fisheries Research Foundation',
        'conservation-through-education':               'Conservation Through Education',
        'plum-beach-lighthouse':                        'Plum Beach Lighthouse',
        'ponham-rocks-lighthouse':                      'Ponham Rocks Lighthouse',
        'rocky-point-foundation':                       'Rocky Point Foundation',
        'rose-island-lighthouse':                       'Rose Island Lighthouse',
        'wildlife-rehabilitators':                      'Wildlife Rehabilitators',
        # Sports
        'boston-bruins-foundation':                     'Boston Bruins Foundation',
        'new-england-patriots':                         'New England Patriots',
        'red-sox-foundation':                           'Red Sox Foundation',
    }

    name_text  = NAME_OVERRIDES.get(core, to_title(core_raw))
    plate_name = f'RI - {name_text}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'ri-standard-issue':
        if 'sailboat' in core:
            series           = RI_ALT_SAIL_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'shark' in core:
            series           = RI_ALT_SHARK_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif core in ('standard-issue-ocean', 'motorcycle', 'alternative-issue-wave'):
            series           = RI_STD_OCEAN_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        else:
            # antique, camper, custom-vehicle, electric-hybrid*, radio-operator,
            # street-rod, suburban — specialty class variants on Ocean base
            series           = RI_STD_OCEAN_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'ri-non-passenger-government':
        if 'sailboat' in core:
            series           = RI_ALT_SAIL_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        elif 'shark' in core:
            series           = RI_ALT_SHARK_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        elif core == 'farm':
            series           = RI_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Agricultural'], 88
        elif core == 'public-service':
            series           = RI_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Government / Exempt'], 90
        elif core == 'trailer':
            series           = RI_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80
        else:
            # combination, commercial, electric-hybrid variants — Ocean base
            series           = RI_STD_OCEAN_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'ri-military':
        series = RI_VET_SERIES
        if 'disabled-veteran' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif sub == 'ri-first-responder':
        series           = RI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'ri-specialty':
        series = RI_SPECIALTY_SERIES
        if any(x in core for x in ('autism', 'cancer', 'breast', 'knock-out')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif 'boy-scouts' in core:
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        elif any(x in core for x in ('bristol-fourth', 'gaspee', 'day-of-portugal')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif 'community-food-bank' in core:
            cat_id, cat_conf = CAT['Health & Awareness'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'ri-outdoors':
        series = RI_SPECIALTY_SERIES
        if any(x in core for x in ('lighthouse', 'rocky-point')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 88

    elif sub == 'ri-school':
        series           = RI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif sub == 'ri-sports':
        series           = RI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Sports Team'], 90

    else:
        series           = RI_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     40,
        'notes':         [],
        'src_subfolder': subfolder,
    }


# ── SC parser ─────────────────────────────────────────────────────────────────
def parse_sc(stem: str, subfolder: str, actual_filename: str):
    """Parse a single SC (South Carolina) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      sc-standard-issue:
        standard-issue-2016-while         → SC_STD_SERIES (819), Standard Issue
        personalized / personalized-disabled → SC_PERS_SERIES (821)
        all others                        → SC_SPECIALTY_SERIES (820)
      all other subfolders               → SC_SPECIALTY_SERIES (820)

    Skip: stems containing ' - Copy' (duplicate files).
    V-variants: -v1/-v2 suffix stripped for routing/lookup, appended as ' - V1'/' - V2' in name.
    Abbreviations auto-expanded: Univ→University, Assn→Association, Foundn→Foundation.
    """
    if not stem.lower().startswith('sc-'):
        return None

    # Skip - Copy duplicates
    if ' - Copy' in stem:
        return None

    core_raw = stem[3:]        # strip 'sc-'
    core     = core_raw.lower()

    # ── V-variant suffix detection ────────────────────────────────────────────
    v_suffix = ''
    m_v = re.match(r'^(.+)-v(\d+)$', core)
    if m_v:
        v_num        = m_v.group(2)
        v_suffix     = f' - V{v_num}'
        core         = m_v.group(1)
        core_raw     = core_raw[:-(len(v_num) + 2)]   # strip '-vN'

    # ── Vehicle class ─────────────────────────────────────────────────────────
    vehicle_class = 'Passenger'
    if core.endswith('-motorcycle') or core == 'motorcycle':
        vehicle_class = 'Motorcycle'
    elif core == 'farm-vehicle':
        vehicle_class = 'Commercial'

    # ── Abbreviation expander ─────────────────────────────────────────────────
    def _expand(name: str) -> str:
        name = re.sub(r'\bUniv\b',   'University', name)
        name = re.sub(r'\bAssn\b',   'Association', name)
        name = re.sub(r'\bFoundn\b', 'Foundation', name)
        return name

    # ── Name overrides ────────────────────────────────────────────────────────
    NAME_OVERRIDES = {
        # Standard issue
        'standard-issue-2016-while':                            'Standard Issue - 2016 - While I Breathe I Hope',
        'standard-issue-2026-revolutionary':                    'Standard Issue - 2026 - Revolutionary',
        'alternative-issue-igwt':                               'Alternative Issue - In God We Trust',
        'personalized':                                         'Personalized',
        'personalized-disabled':                                'Personalized - Disabled',
        'disabled':                                             'Disabled',
        'amateur-radio':                                        'Amateur Radio',
        # Military — typo fix
        'operating-enduring-freedom':                           'Operation Enduring Freedom',
        # Military — HL Hunley
        'hl-hunley':                                            'HL Hunley',
        # Military — US* (to_title gives 'Us')
        'us-air-force-reserve':                                 'US Air Force Reserve',
        'us-armed-forces-retired':                              'US Armed Forces - Retired',
        'us-army-reserve':                                      'US Army Reserve',
        'us-coast-guard-reserve':                               'US Coast Guard Reserve',
        'us-marine-corps-reserve':                              'US Marine Corps Reserve',
        'us-naval-academy':                                     'US Naval Academy',
        'us-navy-chief-petty-officer':                          'US Navy Chief Petty Officer',
        'us-navy-reserve':                                      'US Navy Reserve',
        'us-submarine-veterans':                                'US Submarine Veterans',
        # Schools
        'us-air-force-academy':                                 'US Air Force Academy',
        'west-point':                                           'West Point',
        # Schools — USC plates (to_title gives 'Usc')
        'usc-upstate':                                          'USC Upstate',
        # Sports — USC plates
        'usc-2017-2022-womens-basketball-national-champions':   "USC - 2017-2022 Women's Basketball National Champions",
        'usc-3x-womens-basketball-champions':                   "USC - 3x Women's Basketball Champions",
        'usc-assn-of-letterman':                                'USC - Association of Letterman',
        'usc-baseball-national-champions':                      'USC - Baseball National Champions',
        # Sports — NASCAR
        'nascar':                                               'NASCAR',
        'nascar-darlington-established-1950':                   'NASCAR - Darlington - Established 1950',
        'nascar-darlington-too-tough-to-tame':                  'NASCAR - Darlington - Too Tough to Tame',
        # Sports — Clemson championship
        'clemson-2016-national-football-championship':          'Clemson - 2016 National Football Championship',
        'clemson-2018-national-football-championship':          'Clemson - 2018 National Football Championship',
        'clemson-univ-men-soccer-4x-champions':                 "Clemson University Men's Soccer 4x Champions",
        # Outdoors
        'trees-sc':                                             'Trees SC',
        # Specialty — apostrophes / proper nouns
        'cattlemens-assn':                                      "Cattlemen's Association",
        "childrens-hospital-of-greenville-health-system":       "Children's Hospital of Greenville Health System",
        'choose-life-sc':                                       'Choose Life SC',
        'connie-maxwell-childrens-ministry':                    "Connie Maxwell Children's Ministry",
        'dr-mary-mcleod-bethune':                               'Dr. Mary McLeod Bethune',
        'homeownership-the-american-dream':                     'Homeownership - The American Dream',
        'musc-childrens-hospital':                              "MUSC Children's Hospital",
        'palmetto-health-childrens-hospital':                   "Palmetto Health Children's Hospital",
        'ronald-mcdonald-house-charities':                      'Ronald McDonald House Charities',
        'saint-jude-childrens-hospital':                        "Saint Jude Children's Hospital",
        'www-ibelievesc-net':                                   'www.ibelieveSC.net',
    }

    name_text  = NAME_OVERRIDES.get(core, _expand(to_title(core_raw)))
    plate_name = f'SC - {name_text}{v_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'sc-standard-issue':
        if core == 'standard-issue-2016-while':
            series           = SC_STD_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif core in ('personalized', 'personalized-disabled'):
            series   = SC_PERS_SERIES
            cat_id   = CAT['Disabled / Accessibility'] if 'disabled' in core else CAT['Other / Specialty']
            cat_conf = 90 if 'disabled' in core else 80
        elif core == 'disabled':
            series           = SC_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        elif core == 'amateur-radio':
            series           = SC_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif core == 'motorcycle':
            series           = SC_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif 'standard-issue' in core or 'alternative-issue' in core:
            series           = SC_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        else:
            series           = SC_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'sc-military-veteran':
        series = SC_SPECIALTY_SERIES
        if 'disabled' in core:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif sub == 'sc-first-responder':
        series           = SC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'sc-fraternal':
        series           = SC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Fraternal / Civic'], 85

    elif sub == 'sc-outdoors':
        series = SC_SPECIALTY_SERIES
        if core == 'farm-vehicle':
            cat_id, cat_conf = CAT['Agricultural'], 88
        else:
            cat_id, cat_conf = CAT['Conservation / Environment'], 88

    elif sub == 'sc-schools':
        series           = SC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['School'], 95

    elif sub == 'sc-specialty':
        series = SC_SPECIALTY_SERIES
        if any(x in core for x in ('autism', 'cancer', 'sclerosis', 'childrens-hospital',
                                    'musc', 'saint-jude', 'palmetto-health', 'ronald-mcdonald',
                                    'nurses-found', 'donate-life', 'drivers-for-a-cure',
                                    'no-more-homeless', 'connie-maxwell', 'chase-away',
                                    'respiratory', 'breast-cancer', 'red-cross',
                                    'american-red-cross', 'autistic-neurodivergent')):
            cat_id, cat_conf = CAT['Health & Awareness'], 90
        elif any(x in core for x in ('catawba-nation', 'penn-center', 'dr-mary',
                                      'beaufort-water')):
            cat_id, cat_conf = CAT['Historical / Commemorative'], 85
        elif any(x in core for x in ('boy-scouts', 'eagle-scouts', 'cattlemens',
                                      'chiropractic-assn', 'motorcycle-awareness',
                                      'assn-for-pupil', 'aviation-assn',
                                      'technology-alliance', 'public-education',
                                      'parrothead', 'shag', 'square-dance')):
            cat_id, cat_conf = CAT['Fraternal / Civic'], 85
        else:
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'sc-sports':
        series = SC_SPECIALTY_SERIES
        if 'special-olympics' in core:
            cat_id, cat_conf = CAT['Health & Awareness'], 85
        elif 'share-the-road' in core:
            cat_id, cat_conf = CAT['Conservation / Environment'], 80
        else:
            cat_id, cat_conf = CAT['Sports Team'], 90

    elif sub == 'sc-non-passenger':
        series           = SC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 80

    else:
        series           = SC_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     41,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_ut(stem: str, subfolder: str, actual_filename: str):
    """Parse a single UT (Utah) plate from multi-subfolder structure.

    Series routing:
      833 (Alt - Skier)        — ut-skier-life-elevated, ut-skier-disabled, ut-skier-exempt
      834 (Alt - Arches)       — ut-arches-life-elevated, ut-arches-disabled
      835 (Std - Centennial)   — ut-arches-centennial
      836 (Std - 1985 - Skier) — ut-standard-issue-1985-ski-utah
      837 (Std - 1973 - UTAH)  — ut-standard-issue-1973-utah
      838 (Specialty)          — everything else (all non-standard-issue subfolders +
                                  ut-alt-blackout, ut-in-god-we-trust)
    """
    suffix = actual_filename.rsplit('.', 1)[-1].lower() if '.' in actual_filename else 'png'

    # (plate_name, cat_id, cat_conf, vehicle_class, series_dict)
    NAME_OVERRIDE = {
        # ── ut-standard-issue — series-specific ──────────────────────────────
        'ut-skier-life-elevated':          ('UT - Skier - Life Elevated',              CAT['Standard Issue'],              90, 'Passenger',  UT_ALT_SKIER),
        'ut-skier-disabled':               ('UT - Skier - Disabled',                   CAT['Disabled / Accessibility'],    90, 'Passenger',  UT_ALT_SKIER),
        'ut-skier-exempt':                 ('UT - Skier - Exempt',                     CAT['Government / Exempt'],         88, 'Passenger',  UT_ALT_SKIER),
        'ut-arches-life-elevated':         ('UT - Arches - Life Elevated',             CAT['Standard Issue'],              90, 'Passenger',  UT_ALT_ARCHES),
        'ut-arches-disabled':              ('UT - Arches - Disabled',                  CAT['Disabled / Accessibility'],    90, 'Passenger',  UT_ALT_ARCHES),
        'ut-arches-centennial':            ('UT - Standard Issue - Centennial',        CAT['Standard Issue'],              90, 'Passenger',  UT_STD_CENTENNIAL),
        'ut-standard-issue-1985-ski-utah': ('UT - Standard Issue - 1985 - Ski Utah',  CAT['Standard Issue'],              90, 'Passenger',  UT_STD_1985),
        'ut-standard-issue-1973-utah':     ('UT - Standard Issue - 1973 - UTAH',      CAT['Standard Issue'],              90, 'Passenger',  UT_STD_1973),
        'ut-alt-blackout':                 ('UT - Alt - Blackout',                     CAT['Standard Issue'],              88, 'Passenger',  UT_SPECIALTY),
        'ut-in-god-we-trust':              ('UT - In God We Trust',                    CAT['Standard Issue'],              88, 'Passenger',  UT_SPECIALTY),
        # ── ut-first-responder → 838 ─────────────────────────────────────────
        'ut-civil-air-patrol':             ('UT - Civil Air Patrol',                   CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        'ut-emt':                          ('UT - EMT',                                CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        'ut-fire-fighter':                 ('UT - Fire Fighter',                       CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        'ut-highway-patrol':               ('UT - Highway Patrol',                     CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        'ut-honoring-heroes':              ('UT - Honoring Heroes',                    CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        'ut-law-enforcement-memorial':     ('UT - Law Enforcement Memorial',           CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        'ut-search-and-rescue-teams':      ('UT - Search and Rescue Teams',            CAT['First Responder'],             90, 'Passenger',  UT_SPECIALTY),
        # ── ut-fraternal → 838 ───────────────────────────────────────────────
        'ut-masons':                       ('UT - Masons',                             CAT['Fraternal / Civic'],           90, 'Passenger',  UT_SPECIALTY),
        'ut-rotary-international':         ('UT - Rotary International',               CAT['Fraternal / Civic'],           90, 'Passenger',  UT_SPECIALTY),
        # ── ut-military → 838 ────────────────────────────────────────────────
        'ut-air-force':                          ('UT - Air Force',                          CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-air-force-combat-action-medal':      ('UT - Air Force - Combat Action Medal',    CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-american-legion':                    ('UT - American Legion',                    CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-army':                               ('UT - Army',                               CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-army-combat-action-badge':           ('UT - Army - Combat Action Badge',         CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-army-combat-infantry-badge':         ('UT - Army - Combat Infantry Badge',       CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-coast-guard':                        ('UT - Coast Guard',                        CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-disabled-veteran':                   ('UT - Disabled Veteran',                   CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-former-prisoner-of-war-pow':         ('UT - Former Prisoner of War - POW',       CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-gold-star':                          ('UT - Gold Star',                          CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-marine-navy-combat-action-ribbon':   ('UT - Marine Navy - Combat Action Ribbon', CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-marines':                            ('UT - Marines',                            CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-national-guard':                     ('UT - National Guard',                     CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-navy':                               ('UT - Navy',                               CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-pearl-harbor-survivor':              ('UT - Pearl Harbor Survivor',              CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        'ut-purple-heart-combat-wounded':        ('UT - Purple Heart - Combat Wounded',      CAT['Military / Veteran'],  90, 'Passenger', UT_SPECIALTY),
        # ── ut-non-passenger-government → 838 ───────────────────────────────
        'ut-amateur-radio':           ('UT - Amateur Radio',          CAT['Radio / Amateur Radio'],   92, 'Passenger',  UT_SPECIALTY),
        'ut-farm-vehicle':            ('UT - Farm Vehicle',           CAT['Agricultural'],            90, 'Commercial', UT_SPECIALTY),
        'ut-honorary-consul':         ('UT - Honorary Consul',        CAT['Government / Exempt'],     88, 'Passenger',  UT_SPECIALTY),
        'ut-off-highway-vehicle':     ('UT - Off-Highway Vehicle',    CAT['Government / Exempt'],     88, 'ATV',        UT_SPECIALTY),
        'ut-snowmobiler':             ('UT - Snowmobiler',            CAT['Other / Specialty'],       88, 'Snowmobile', UT_SPECIALTY),
        'ut-special-interest-vehicle':('UT - Special Interest Vehicle',CAT['Other / Specialty'],     88, 'Passenger',  UT_SPECIALTY),
        'ut-state-legislator':        ('UT - State Legislator',       CAT['Government / Exempt'],     88, 'Passenger',  UT_SPECIALTY),
        'ut-united-state-congress':   ('UT - United States Congress', CAT['Government / Exempt'],     88, 'Passenger',  UT_SPECIALTY),
        # ── ut-outdoors → 838 ────────────────────────────────────────────────
        'ut-clean-fuel-clean-air': ('UT - Clean Fuel - Clean Air',  CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-wildlife-eagle':       ('UT - Wildlife - Eagle',         CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-wildlife-elk':         ('UT - Wildlife - Elk',           CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-wildlife-kestrel':     ('UT - Wildlife - Kestrel',       CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-wildlife-mule-deer':   ('UT - Wildlife - Mule Deer',     CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-wildlife-trout':       ('UT - Wildlife - Trout',         CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-zion-national-park':   ('UT - Zion National Park',       CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        # ── ut-schools → 838 ─────────────────────────────────────────────────
        'ut-brigham-young-university':     ('UT - Brigham Young University',     CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-college-of-eastern-utah':      ('UT - College of Eastern Utah',      CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-ensign-college':               ('UT - Ensign College',               CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-salt-lake-community-college':  ('UT - Salt Lake Community College',  CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-snow-college':                 ('UT - Snow College',                 CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-southern-utah-university':     ('UT - Southern Utah University',     CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-university-of-utah-v1':        ('UT - University of Utah - V1',      CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-university-of-utah-v2':        ('UT - University of Utah - V2',      CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-utah-state-university':        ('UT - Utah State University',        CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-utah-tech-university':         ('UT - Utah Tech University',         CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-utah-valley-university':       ('UT - Utah Valley University',       CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-weber-state-university':       ('UT - Weber State University',       CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-western-governors-university': ('UT - Western Governors University', CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-westminster-college':          ('UT - Westminster College',          CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        'ut-westminster-college.v2':       ('UT - Westminster College - V2',     CAT['School'], 90, 'Passenger', UT_SPECIALTY),
        # ── ut-specialty → 838 ───────────────────────────────────────────────
        'ut-autism-awareness':           ('UT - Autism Awareness',          CAT['Health & Awareness'],          90, 'Passenger', UT_SPECIALTY),
        'ut-boys-and-girls-clubs':       ('UT - Boys and Girls Clubs',      CAT['Fraternal / Civic'],           90, 'Passenger', UT_SPECIALTY),
        'ut-boy-scouts-of-america':      ('UT - Boy Scouts of America',     CAT['Fraternal / Civic'],           90, 'Passenger', UT_SPECIALTY),
        'ut-cancer-research':            ('UT - Cancer Research',           CAT['Health & Awareness'],          90, 'Passenger', UT_SPECIALTY),
        'ut-childrens-issues':           ('UT - Childrens Issues',          CAT['Health & Awareness'],          88, 'Passenger', UT_SPECIALTY),
        'ut-disabled':                   ('UT - Disabled',                  CAT['Disabled / Accessibility'],    90, 'Passenger', UT_SPECIALTY),
        'ut-disabled-person':            ('UT - Disabled Person',           CAT['Disabled / Accessibility'],    90, 'Passenger', UT_SPECIALTY),
        'ut-donate-life':                ('UT - Donate Life',               CAT['Health & Awareness'],          90, 'Passenger', UT_SPECIALTY),
        'ut-great-salt-lake-preservation':('UT - Great Salt Lake Preservation', CAT['Conservation / Environment'], 90, 'Passenger', UT_SPECIALTY),
        'ut-homeless-pets':              ('UT - Homeless Pets',             CAT['Health & Awareness'],          88, 'Passenger', UT_SPECIALTY),
        'ut-housing-opportunity-realtor':('UT - Housing Opportunity - Realtor', CAT['Other / Specialty'],       88, 'Passenger', UT_SPECIALTY),
        'ut-martin-luther-king':         ('UT - Martin Luther King',        CAT['Historical / Commemorative'],  88, 'Passenger', UT_SPECIALTY),
        'ut-prostate-cancer-awareness':  ('UT - Prostate Cancer Awareness', CAT['Health & Awareness'],          90, 'Passenger', UT_SPECIALTY),
        'ut-public-education-support':   ('UT - Public Education Support',  CAT['Other / Specialty'],           88, 'Passenger', UT_SPECIALTY),
        'ut-soil-conservation':          ('UT - Soil Conservation',         CAT['Conservation / Environment'],  90, 'Passenger', UT_SPECIALTY),
        'ut-suicide-prevention':         ('UT - Suicide Prevention',        CAT['Health & Awareness'],          90, 'Passenger', UT_SPECIALTY),
        'ut-vintage-vehicle':            ('UT - Vintage Vehicle',           CAT['Historical / Commemorative'],  88, 'Passenger', UT_SPECIALTY),
        'ut-womens-suffrage':            ('UT - Womens Suffrage',           CAT['Historical / Commemorative'],  88, 'Passenger', UT_SPECIALTY),
        # ── ut-sports → 838 ──────────────────────────────────────────────────
        'ut-olympic':       ('UT - Olympic',        CAT['Sports Team'],       90, 'Passenger', UT_SPECIALTY),
        'ut-real-salt-lake':('UT - Real Salt Lake', CAT['Sports Team'],       90, 'Passenger', UT_SPECIALTY),
        'ut-share-the-road':('UT - Share the Road', CAT['Other / Specialty'], 88, 'Passenger', UT_SPECIALTY),
        'ut-utah-jazz':     ('UT - Utah Jazz',       CAT['Sports Team'],       90, 'Passenger', UT_SPECIALTY),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class, series = NAME_OVERRIDE[stem]

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     45,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_pe(stem: str, subfolder: str, actual_filename: str):
    """Parse a single PE (Prince Edward Island) plate from multi-subfolder structure.

    Series routing:
      Series 830 (Alt)  — all pe-alt-* prefixed stems + pe-dealer + pe-atv-dealer
      Series 829 (Std)  — everything else

    One stem is skipped as a duplicate:
      pe-alt-motocycle-personalized-graphic-french  (typo dup of the grahpic variant)
    """
    SKIP = {'pe-alt-motocycle-personalized-graphic-french'}
    if stem in SKIP:
        return None

    suffix = actual_filename.rsplit('.', 1)[-1].lower() if '.' in actual_filename else 'png'

    # (plate_name, cat_id, cat_conf, vehicle_class, series_id)
    NAME_OVERRIDE = {
        # ── pe-first-responder ───────────────────────────────────────────────
        'pe-alt-paramedic-english':               ('PE - Alt - Paramedic - English',                           CAT['First Responder'],             90, 'Passenger',  830),
        'pe-alt-paramedic-french':                ('PE - Alt - Paramedic - French',                            CAT['First Responder'],             90, 'Passenger',  830),
        'pe-firefighter-motorcycle':              ('PE - Firefighter - Motorcycle',                             CAT['First Responder'],             90, 'Motorcycle', 829),
        'pe-firefighter-volunteer':               ('PE - Firefighter - Volunteer',                              CAT['First Responder'],             90, 'Passenger',  829),
        'pe-ground-search-and-rescue-motorcycle': ('PE - Ground Search and Rescue - Motorcycle',                CAT['First Responder'],             90, 'Motorcycle', 829),
        'pe-ground-search-and-rescue-v1':         ('PE - Ground Search and Rescue - V1',                       CAT['First Responder'],             90, 'Passenger',  829),
        'pe-ground-search-and-rescue-v2':         ('PE - Ground Search and Rescue - V2',                       CAT['First Responder'],             90, 'Passenger',  829),
        # ── pe-non-passenger-government ─────────────────────────────────────
        'pe-atv-dealer':                          ('PE - ATV Dealer',                                          CAT['Dealer / Manufacturer'],       90, 'ATV',        830),
        'pe-atv-english':                         ('PE - ATV - English',                                       CAT['Government / Exempt'],         88, 'ATV',        829),
        'pe-commercial':                          ('PE - Commercial',                                          CAT['Government / Exempt'],         88, 'Commercial', 829),
        'pe-dealer':                              ('PE - Dealer',                                              CAT['Dealer / Manufacturer'],       90, 'Passenger',  830),
        'pe-farm-truck':                          ('PE - Farm Truck',                                          CAT['Agricultural'],                90, 'Commercial', 829),
        'pe-government-vehicle':                  ('PE - Government Vehicle',                                  CAT['Government / Exempt'],         88, 'Passenger',  829),
        'pe-prorate':                             ('PE - Prorate',                                             CAT['Government / Exempt'],         88, 'Commercial', 829),
        'pe-special-mobile':                      ('PE - Special Mobile',                                      CAT['Government / Exempt'],         88, 'Commercial', 829),
        'pe-special-vehicle':                     ('PE - Special Vehicle',                                     CAT['Government / Exempt'],         88, 'Passenger',  829),
        'pe-trailer':                             ('PE - Trailer',                                             CAT['Government / Exempt'],         88, 'Trailer',    829),
        'pe-trailer-french':                      ('PE - Trailer - French',                                    CAT['Government / Exempt'],         88, 'Trailer',    829),
        'pe-transporter':                         ('PE - Transporter',                                         CAT['Government / Exempt'],         88, 'Commercial', 829),
        # ── pe-outdoor-conservation ─────────────────────────────────────────
        'pe-conservation-blue-jay-english':       ('PE - Conservation - Blue Jay - English',                   CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-blue-jay-french':        ('PE - Conservation - Blue Jay - French',                    CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-fox':                    ('PE - Conservation - Fox',                                  CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-fox-french':             ('PE - Conservation - Fox - French',                         CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-goose':                  ('PE - Conservation - Goose',                                CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-goose-french':           ('PE - Conservation - Goose - French',                       CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-ladyslipper':            ('PE - Conservation - Ladyslipper',                          CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-ladyslipper-french':     ('PE - Conservation - Ladyslipper - French',                 CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-trout':                  ('PE - Conservation - Trout',                                CAT['Conservation / Environment'],  90, 'Passenger',  829),
        'pe-conservation-trout-french':           ('PE - Conservation - Trout - French',                       CAT['Conservation / Environment'],  90, 'Passenger',  829),
        # ── pe-specialty ────────────────────────────────────────────────────
        'pe-food-island-english':                 ('PE - Food Island - English',                               CAT['Other / Specialty'],           88, 'Passenger',  829),
        'pe-food-island-french':                  ('PE - Food Island - French',                                CAT['Other / Specialty'],           88, 'Passenger',  829),
        # ── pe-standard-issue ───────────────────────────────────────────────
        'pe-alt-amateur-radio-english':                   ('PE - Alt - Amateur Radio - English',                       CAT['Radio / Amateur Radio'],       92, 'Passenger',  830),
        'pe-alt-amateur-radio-french':                    ('PE - Alt - Amateur Radio - French',                        CAT['Radio / Amateur Radio'],       92, 'Passenger',  830),
        'pe-alt-english':                                 ('PE - Alt - English',                                       CAT['Standard Issue'],              90, 'Passenger',  830),
        'pe-alt-french':                                  ('PE - Alt - French',                                        CAT['Standard Issue'],              90, 'Passenger',  830),
        'pe-alt-motorcycle-personalized-grahpic-french':  ('PE - Alt - Motorcycle - Personalized - Graphic - French',  CAT['Standard Issue'],              90, 'Motorcycle', 830),
        'pe-alt-motorcycle-personalized-plain-french':    ('PE - Alt - Motorcycle - Personalized - Plain - French',    CAT['Standard Issue'],              90, 'Motorcycle', 830),
        'pe-alt-motorcycle-personalized-plain-french-v2': ('PE - Alt - Motorcycle - Personalized - Plain - French - V2', CAT['Standard Issue'],            90, 'Motorcycle', 830),
        'pe-alt-personalized-graphic-english':            ('PE - Alt - Personalized - Graphic - English',               CAT['Standard Issue'],              90, 'Passenger',  830),
        'pe-alt-personalized-graphic-french':             ('PE - Alt - Personalized - Graphic - French',                CAT['Standard Issue'],              90, 'Passenger',  830),
        'pe-alt-personalized-plain-english':              ('PE - Alt - Personalized - Plain - English',                 CAT['Standard Issue'],              90, 'Passenger',  830),
        'pe-alt-personalized-plain-french':               ('PE - Alt - Personalized - Plain - French',                  CAT['Standard Issue'],              90, 'Passenger',  830),
        'pe-collector':                                   ('PE - Collector',                                            CAT['Other / Specialty'],           88, 'Passenger',  829),
        'pe-collector-french':                            ('PE - Collector - French',                                   CAT['Other / Specialty'],           88, 'Passenger',  829),
        'pe-electric-vehicle-english':                    ('PE - Electric Vehicle - English',                           CAT['Standard Issue'],              90, 'Passenger',  829),
        'pe-electric-vehicle-french':                     ('PE - Electric Vehicle - French',                            CAT['Standard Issue'],              90, 'Passenger',  829),
        'pe-moped-english':                               ('PE - Moped - English',                                      CAT['Standard Issue'],              88, 'Motorcycle', 829),
        'pe-moped-french':                                ('PE - Moped - French',                                       CAT['Standard Issue'],              88, 'Motorcycle', 829),
        'pe-motorcycle-personalized-plain-english':       ('PE - Motorcycle - Personalized - Plain - English',          CAT['Standard Issue'],              90, 'Motorcycle', 829),
        'pe-snomobile':                                   ('PE - Snowmobile',                                           CAT['Standard Issue'],              88, 'Snowmobile', 829),
        'pe-snomobile-french':                            ('PE - Snowmobile - French',                                  CAT['Standard Issue'],              88, 'Snowmobile', 829),
        'pe-standard-issue-english':                      ('PE - Standard Issue - English',                             CAT['Standard Issue'],              90, 'Passenger',  829),
        'pe-standard-issue-french':                       ('PE - Standard Issue - French',                              CAT['Standard Issue'],              90, 'Passenger',  829),
        'pe-vintage-cruisers':                            ('PE - Vintage Cruisers',                                     CAT['Historical / Commemorative'],  88, 'Passenger',  829),
        # ── pe-veteran ──────────────────────────────────────────────────────
        'pe-alt-veteran-english':              ('PE - Alt - Veteran - English',            CAT['Military / Veteran'],  90, 'Passenger', 830),
        'pe-coast-guard-auxiliary-passenger':  ('PE - Coast Guard Auxiliary - Passenger',  CAT['Military / Veteran'],  90, 'Passenger', 829),
        'pe-standard-issue-veteran-english':   ('PE - Standard Issue - Veteran - English', CAT['Military / Veteran'],  90, 'Passenger', 829),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class, series_id = NAME_OVERRIDE[stem]

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series_id,
        'series_conf':   95,
        'region_id':     61,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_sk(stem: str, actual_filename: str):
    """Parse a single SK (Saskatchewan) plate image from flat folder.

    All 11 plates map to SK_SERIES (825), region_id 63.

    Name overrides (stem → plate_name, category, vehicle_class):
      sk-alternative-issue-2011-personalized  → SK - Alternative Issue - 2011 - Personalized  / Standard Issue    / Passenger
      sk-collector                            → SK - Collector                                  / Other            / Passenger
      sk-memorial-cross                       → SK - Memorial Cross                             / Military/Veteran / Passenger
      sk-roughriders-v1                       → SK - Roughriders - V1                           / Sports Team      / Passenger
      sk-roughriders-v2                       → SK - Roughriders - V2                           / Sports Team      / Passenger
      sk-rush                                 → SK - Rush                                        / Sports Team      / Passenger
      sk-spca                                 → SK - SPCA                                        / Health/Awareness / Passenger
      sk-standard-issue-2022-land-of-living-skies → SK - Standard Issue - 2022 - Land of Living Skies / Standard Issue / Passenger
      sk-standard-issue-disabled              → SK - Standard Issue - Disabled                  / Disabled         / Passenger
      sk-support-our-troops                   → SK - Support Our Troops                          / Military/Veteran / Passenger
      sk-veteran                              → SK - Veteran                                     / Military/Veteran / Passenger
    """
    suffix = actual_filename.rsplit('.', 1)[-1].lower() if '.' in actual_filename else 'png'

    NAME_OVERRIDE = {
        'sk-alternative-issue-2011-personalized':     ('SK - Alternative Issue - 2011 - Personalized',       CAT['Standard Issue'],           90, 'Passenger'),
        'sk-collector':                               ('SK - Collector',                                      CAT['Other / Specialty'],        90, 'Passenger'),
        'sk-memorial-cross':                          ('SK - Memorial Cross',                                 CAT['Military / Veteran'],       90, 'Passenger'),
        'sk-roughriders-v1':                          ('SK - Roughriders - V1',                               CAT['Sports Team'],              90, 'Passenger'),
        'sk-roughriders-v2':                          ('SK - Roughriders - V2',                               CAT['Sports Team'],              90, 'Passenger'),
        'sk-rush':                                    ('SK - Rush',                                           CAT['Sports Team'],              90, 'Passenger'),
        'sk-spca':                                    ('SK - SPCA',                                           CAT['Health & Awareness'],       90, 'Passenger'),
        'sk-standard-issue-2022-land-of-living-skies':('SK - Standard Issue - 2022 - Land of Living Skies',  CAT['Standard Issue'],           90, 'Passenger'),
        'sk-standard-issue-disabled':                 ('SK - Standard Issue - Disabled',                     CAT['Disabled / Accessibility'], 90, 'Passenger'),
        'sk-support-our-troops':                      ('SK - Support Our Troops',                             CAT['Military / Veteran'],       90, 'Passenger'),
        'sk-veteran':                                 ('SK - Veteran',                                        CAT['Military / Veteran'],       90, 'Passenger'),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class = NAME_OVERRIDE[stem]

    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     SK_SERIES['id'],
        'series_conf':   SK_SERIES['conf'],
        'region_id':     63,
        'notes':         [],
        'src_subfolder': '',
    }


def parse_sd(stem: str, subfolder: str, actual_filename: str):
    """Parse a single SD (South Dakota) plate image from multi-subfolder structure.

    Subfolder → Series routing:
      sd-standard-issue:
        standard-issue-2006-great-faces → SD_STD_SERIES (822), Standard Issue
        personalized / rear-only        → SD_STD_SERIES (822), Other / Specialty
        amateur-radio                   → SD_SPECIALTY_SERIES (823), Radio / Amateur Radio
        permanently-disabled-person*    → SD_WHITE_SERIES (824), Disabled / Accessibility
      sd-military-veteran               → SD_SPECIALTY_SERIES (823), Military / Veteran
                                          (disabled-veteran* → Disabled / Accessibility)
      sd-first-nation                   → SD_WHITE_SERIES (824), Historical / Commemorative
                                          (-veteran variants → Military / Veteran)
      sd-first-responder                → SD_SPECIALTY_SERIES (823), First Responder
      sd-non-passenger-government       → SD_SPECIALTY_SERIES (823), Government / Exempt
      sd-specialty                      → SD_SPECIALTY_SERIES (823), Conservation / Environment

    Vehicle class modifiers (detected by filename suffix):
      -motorcycle-active-duty → Motorcycle, qualifier ' - Active Duty'
      -vehicle-active-duty    → Passenger,  qualifier ' - Vehicle - Active Duty'
      -woman-veteran-vehicle  → Passenger,  qualifier ' - Woman Veteran - Vehicle'
      -motorcycle / -motorcyle (typo fix) → Motorcycle, qualifier ' - Motorcycle'
      construction-vehicle    → Commercial
      school                  → Other

    First Nation plates: all routed to SD_WHITE_SERIES (824) — review on proofread.
    Typo fix: 'navy-cross-motorcyle' filename → correct name 'Navy Cross - Motorcycle'.
    """
    if not stem.lower().startswith('sd-'):
        return None
    if ' - Copy' in stem:
        return None

    core_raw = stem[3:]        # strip 'sd-'
    core     = core_raw.lower()

    # ── V-variant suffix detection ────────────────────────────────────────────
    v_suffix = ''
    m_v = re.match(r'^(.+)-v(\d+)$', core)
    if m_v:
        v_num    = m_v.group(2)
        v_suffix = f' - V{v_num}'
        core     = m_v.group(1)
        core_raw = core_raw[:-(len(v_num) + 2)]

    # ── Vehicle class + qualifier extraction ──────────────────────────────────
    vehicle_class = 'Passenger'
    qual          = ''      # appended to base name: ' - Qualifier'
    base          = core    # core after stripping vehicle/modifier suffixes

    # Branch names that have BOTH a plain -motorcycle.png AND a
    # -motorcycle-active-duty.png in sd-military-veteran.  The plain one is
    # a duplicate of the active-duty variant, so it is skipped (return None).
    _ACTIVE_DUTY_BRANCHES = {
        'air-force', 'army', 'coast-guard', 'marine', 'navy',
    }

    if base.endswith('-motorcycle-active-duty'):
        vehicle_class = 'Motorcycle'
        qual          = ' - Active Duty'
        base          = base[:-len('-motorcycle-active-duty')]
    elif base.endswith('-vehicle-active-duty'):
        qual = ' - Vehicle - Active Duty'
        base = base[:-len('-vehicle-active-duty')]
    elif base.endswith('-woman-veteran-vehicle'):
        qual = ' - Woman Veteran - Vehicle'
        base = base[:-len('-woman-veteran-vehicle')]
    elif base.endswith('-motorcyle'):      # typo in filename: missing 'c'
        vehicle_class = 'Motorcycle'
        qual          = ' - Motorcycle'
        base          = base[:-len('-motorcyle')]
    elif base.endswith('-motorcycle'):
        stripped_base = base[:-len('-motorcycle')]
        if stripped_base in _ACTIVE_DUTY_BRANCHES:
            # Plain branch motorcycle is a duplicate of -motorcycle-active-duty
            return None
        vehicle_class = 'Motorcycle'
        qual          = ' - Motorcycle'
        base          = stripped_base
    elif base == 'construction-vehicle':
        vehicle_class = 'Commercial'
    elif base == 'school':
        vehicle_class = 'Other'

    # ── Name overrides (keyed on base after modifier stripping) ───────────────
    NAME_OVERRIDES = {
        # Standard issue
        'standard-issue-2006-great-faces':          'Standard Issue - 2006 - Great Faces',
        # Acronyms
        'pow':                                      'POW',
        'ems':                                      'EMS',
        # Preposition fix ('with' not in SMALL_WORDS → would capitalize)
        'bronze-star-with-valor':                   'Bronze Star with Valor',
        # First responder qualifier
        'firefighter-retired':                      'Firefighter - Retired',
        # Space Force qualifiers
        'space-force-veteran':                      'Space Force - Veteran',
        'space-force-woman-veteran':                'Space Force - Woman Veteran',
        # First Nation — tribal veteran variants
        'cheyenne-river-sioux-tribe-veteran':       'Cheyenne River Sioux Tribe - Veteran',
        'crow-creek-sioux-tribe-veteran':           'Crow Creek Sioux Tribe - Veteran',
        'flandreau-santee-sioux-tribe-veteran':     'Flandreau Santee Sioux Tribe - Veteran',
        'lower-brule-sioux-tribe-veteran':          'Lower Brule Sioux Tribe - Veteran',
        'oglala-lakota-sioux-tribe-veteran':        'Oglala Lakota Sioux Tribe - Veteran',
        'rosebud-sioux-tribe-veteran':              'Rosebud Sioux Tribe - Veteran',
        'sisseton-wahpeton-sioux-tribe-veteran':    'Sisseton Wahpeton Sioux Tribe - Veteran',
        'standing-rock-sioux-tribe-veteran':        'Standing Rock Sioux Tribe - Veteran',
    }

    base_name  = NAME_OVERRIDES.get(base, to_title(base))
    plate_name = f'SD - {base_name}{qual}{v_suffix}'

    # ── Series + category routing ─────────────────────────────────────────────
    sub = subfolder.lower()

    if sub == 'sd-standard-issue':
        if base == 'standard-issue-2006-great-faces':
            series           = SD_STD_SERIES
            cat_id, cat_conf = CAT['Standard Issue'], 95
        elif base == 'amateur-radio':
            series           = SD_SPECIALTY_SERIES
            cat_id, cat_conf = CAT['Radio / Amateur Radio'], 95
        elif 'permanently-disabled' in base:
            series           = SD_WHITE_SERIES
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 95
        else:
            # personalized, rear-only
            series           = SD_STD_SERIES
            cat_id, cat_conf = CAT['Other / Specialty'], 80

    elif sub == 'sd-military-veteran':
        series = SD_SPECIALTY_SERIES
        if 'disabled-veteran' in base:
            cat_id, cat_conf = CAT['Disabled / Accessibility'], 90
        else:
            cat_id, cat_conf = CAT['Military / Veteran'], 95

    elif sub == 'sd-first-nation':
        series = SD_WHITE_SERIES
        if base.endswith('-veteran') or 'veteran' in qual.lower():
            cat_id, cat_conf = CAT['Military / Veteran'], 88
        else:
            cat_id, cat_conf = CAT['Historical / Commemorative'], 88

    elif sub == 'sd-first-responder':
        series           = SD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['First Responder'], 95

    elif sub == 'sd-non-passenger-government':
        series           = SD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Government / Exempt'], 90

    elif sub == 'sd-specialty':
        series           = SD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Conservation / Environment'], 88

    else:
        series           = SD_SPECIALTY_SERIES
        cat_id, cat_conf = CAT['Other / Specialty'], 75

    suffix = actual_filename.split('.')[-1]
    return {
        'filename':      f'{stem}.{suffix}',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     42,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_vt(stem: str, subfolder: str, actual_filename: str):
    """Parse a single VT (Vermont) plate image from multi-subfolder structure.

    Series routing:
      Series 839 (Standard Issue) — vt-standard-issue subfolder
      Series 840 (Specialty)      — all other subfolders

    Vehicle class conventions:
      -truck suffix    → Commercial, append ' - Truck' to name
      -motorcycle      → Motorcycle
      -snowmobile      → Snowmobile
      -atv             → ATV (standalone stems only)
      everything else  → Passenger unless overridden below
    """
    NAME_OVERRIDE = {
        # ── vt-standard-issue → 839 ──────────────────────────────────────────
        'vt-amateur-radio-operator':           ('VT - Amateur Radio Operator',                    CAT['Radio / Amateur Radio'],        95, 'Passenger',  VT_STD_SERIES),
        'vt-amateur-radio-operator-truck':     ('VT - Amateur Radio Operator - Truck',            CAT['Radio / Amateur Radio'],        95, 'Commercial', VT_STD_SERIES),
        'vt-antique':                          ('VT - Antique',                                   CAT['Historical / Commemorative'],   90, 'Passenger',  VT_STD_SERIES),
        'vt-antique-motorcycle':               ('VT - Antique - Motorcycle',                      CAT['Historical / Commemorative'],   90, 'Motorcycle', VT_STD_SERIES),
        'vt-antique-snowmobile':               ('VT - Antique - Snowmobile',                      CAT['Historical / Commemorative'],   90, 'Snowmobile', VT_STD_SERIES),
        'vt-atv':                              ('VT - ATV',                                       CAT['Standard Issue'],               88, 'ATV',        VT_STD_SERIES),
        'vt-disabled':                         ('VT - Disabled',                                  CAT['Disabled / Accessibility'],     95, 'Passenger',  VT_STD_SERIES),
        'vt-disabled-motorcycle':              ('VT - Disabled - Motorcycle',                     CAT['Disabled / Accessibility'],     95, 'Motorcycle', VT_STD_SERIES),
        'vt-low-number-100-9999':              ('VT - Low Number - 100-9999',                     CAT['Standard Issue'],               88, 'Passenger',  VT_STD_SERIES),
        'vt-low-number-100-9999-truck':        ('VT - Low Number - 100-9999 - Truck',             CAT['Standard Issue'],               88, 'Commercial', VT_STD_SERIES),
        'vt-low-vermont-numbers':              ('VT - Low Vermont Numbers',                       CAT['Standard Issue'],               88, 'Passenger',  VT_STD_SERIES),
        'vt-motorcycle':                       ('VT - Motorcycle',                                CAT['Standard Issue'],               95, 'Motorcycle', VT_STD_SERIES),
        'vt-motor-driven-cycle':               ('VT - Motor Driven Cycle',                        CAT['Standard Issue'],               90, 'Motorcycle', VT_STD_SERIES),
        'vt-pleasure-car':                     ('VT - Pleasure Car',                              CAT['Standard Issue'],               95, 'Passenger',  VT_STD_SERIES),
        'vt-special-vanity':                   ('VT - Special Vanity',                            CAT['Standard Issue'],               88, 'Passenger',  VT_STD_SERIES),
        'vt-standard-issue-1990':              ('VT - Standard Issue - 1990',                     CAT['Standard Issue'],               95, 'Passenger',  VT_STD_SERIES),
        'vt-street-rod':                       ('VT - Street Rod',                                CAT['Historical / Commemorative'],   88, 'Passenger',  VT_STD_SERIES),
        # ── vt-first-responder → 840 ─────────────────────────────────────────
        'vt-emergency-medical-service':                ('VT - Emergency Medical Service',                     CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-emergency-medical-service-truck':          ('VT - Emergency Medical Service - Truck',             CAT['First Responder'],          90, 'Commercial', VT_SPECIALTY),
        'vt-national-ski-patrol':                      ('VT - National Ski Patrol',                           CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-professional-firefighters-of-vermont':     ('VT - Professional Firefighters of Vermont',          CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-sheriff-department':                       ('VT - Sheriff Department',                            CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-state-police':                             ('VT - State Police',                                  CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-vermont-firefighters-association':         ('VT - Vermont Firefighters Association',              CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-vermont-firefighters-association-truck':   ('VT - Vermont Firefighters Association - Truck',      CAT['First Responder'],          90, 'Commercial', VT_SPECIALTY),
        'vt-vermont-game-warden':                      ('VT - Vermont Game Warden',                           CAT['First Responder'],          90, 'Passenger',  VT_SPECIALTY),
        # ── vt-fraternal → 840 ───────────────────────────────────────────────
        'vt-american-legion':                  ('VT - American Legion',                           CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-american-legion-truck':            ('VT - American Legion - Truck',                   CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-freemasons':                       ('VT - Freemasons',                                CAT['Fraternal / Civic'],            90, 'Passenger',  VT_SPECIALTY),
        'vt-freemasons-truck':                 ('VT - Freemasons - Truck',                        CAT['Fraternal / Civic'],            90, 'Commercial', VT_SPECIALTY),
        'vt-lions-club':                       ('VT - Lions Club',                                CAT['Fraternal / Civic'],            90, 'Passenger',  VT_SPECIALTY),
        'vt-rotary':                           ('VT - Rotary',                                    CAT['Fraternal / Civic'],            90, 'Passenger',  VT_SPECIALTY),
        'vt-rotary-truck':                     ('VT - Rotary - Truck',                            CAT['Fraternal / Civic'],            90, 'Commercial', VT_SPECIALTY),
        # ── vt-military → 840 ────────────────────────────────────────────────
        'vt-ex-prisoner-of-war':               ('VT - Ex-Prisoner of War',                        CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-ex-prisoner-of-war-truck':         ('VT - Ex-Prisoner of War - Truck',                CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-gold-star-family':                 ('VT - Gold Star Family',                          CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-gold-star-next-of-kin':            ('VT - Gold Star - Next of Kin',                   CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-pearl-harbor-survivor':            ('VT - Pearl Harbor Survivor',                     CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-pearl-harbor-survivor-truck':      ('VT - Pearl Harbor Survivor - Truck',             CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-purple-heart':                     ('VT - Purple Heart',                              CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-purple-heart-truck':               ('VT - Purple Heart - Truck',                      CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-us-veteran':                       ('VT - US Veteran',                                CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-truck':                 ('VT - US Veteran - Truck',                        CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-us-veteran-motorcycle':            ('VT - US Veteran - Motorcycle',                   CAT['Military / Veteran'],           90, 'Motorcycle', VT_SPECIALTY),
        'vt-us-veteran-afghanistan-campaign':  ('VT - US Veteran - Afghanistan Campaign',         CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-gulf-war':              ('VT - US Veteran - Gulf War',                     CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-handicap':              ('VT - US Veteran - Handicap',                     CAT['Disabled / Accessibility'],     90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-iraq-campaign':         ('VT - US Veteran - Iraq Campaign',                CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-korean-war':            ('VT - US Veteran - Korean War',                   CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-vietnam-war':           ('VT - US Veteran - Vietnam War',                  CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-us-veteran-world-war-ii':          ('VT - US Veteran - World War II',                 CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-vermont-national-guard':           ('VT - Vermont National Guard',                    CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-vermont-national-guard-truck':     ('VT - Vermont National Guard - Truck',            CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-veterans-of-foreign-wars':         ('VT - Veterans of Foreign Wars',                  CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-veterans-of-foreign-wars-truck':   ('VT - Veterans of Foreign Wars - Truck',          CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        'vt-vietnam-veterans-of-america':      ('VT - Vietnam Veterans of America',               CAT['Military / Veteran'],           90, 'Passenger',  VT_SPECIALTY),
        'vt-vietnam-veterans-of-america-truck':('VT - Vietnam Veterans of America - Truck',       CAT['Military / Veteran'],           90, 'Commercial', VT_SPECIALTY),
        # ── vt-non-passenger-government → 840 ────────────────────────────────
        'vt-agriculture':                          ('VT - Agriculture',                           CAT['Agricultural'],                 90, 'Commercial', VT_SPECIALTY),
        'vt-apportioned-bus':                      ('VT - Apportioned Bus',                       CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-apportioned-truck':                    ('VT - Apportioned Truck',                     CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-atv-dealer':                           ('VT - ATV Dealer',                            CAT['Dealer / Manufacturer'],        90, 'ATV',        VT_SPECIALTY),
        'vt-auction-car-dealer':                   ('VT - Auction Car Dealer',                    CAT['Dealer / Manufacturer'],        90, 'Passenger',  VT_SPECIALTY),
        'vt-bus':                                  ('VT - Bus',                                   CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-car-dealer-new':                       ('VT - Car Dealer - New',                      CAT['Dealer / Manufacturer'],        90, 'Passenger',  VT_SPECIALTY),
        'vt-car-dealer-used':                      ('VT - Car Dealer - Used',                     CAT['Dealer / Manufacturer'],        90, 'Passenger',  VT_SPECIALTY),
        'vt-contractor-trailer':                   ('VT - Contractor Trailer',                    CAT['Government / Exempt'],          88, 'Trailer',    VT_SPECIALTY),
        'vt-dmv':                                  ('VT - DMV',                                   CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-driver-education':                     ('VT - Driver Education',                      CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-exhibition':                           ('VT - Exhibition',                            CAT['Historical / Commemorative'],   88, 'Passenger',  VT_SPECIALTY),
        'vt-farm-machinery-dealer':                ('VT - Farm Machinery Dealer',                 CAT['Dealer / Manufacturer'],        90, 'Commercial', VT_SPECIALTY),
        'vt-federal-program':                      ('VT - Federal Program',                       CAT['Government / Exempt'],          88, 'Passenger',  VT_SPECIALTY),
        'vt-finance-car-dealer':                   ('VT - Finance Car Dealer',                    CAT['Dealer / Manufacturer'],        90, 'Passenger',  VT_SPECIALTY),
        'vt-highway-building-equipment-dealer':    ('VT - Highway Building Equipment Dealer',     CAT['Dealer / Manufacturer'],        88, 'Commercial', VT_SPECIALTY),
        'vt-local-transit-bus':                    ('VT - Local Transit Bus',                     CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-mtc-mdc-dealer':                       ('VT - MTC MDC Dealer',                        CAT['Dealer / Manufacturer'],        88, 'Commercial', VT_SPECIALTY),
        'vt-municipal':                            ('VT - Municipal',                             CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-off-highway-tractor':                  ('VT - Off-Highway Tractor',                   CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-snowmobile-dealer':                    ('VT - Snowmobile Dealer',                     CAT['Dealer / Manufacturer'],        90, 'Snowmobile', VT_SPECIALTY),
        'vt-special-purpose-truck':                ('VT - Special Purpose Truck',                 CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-state-government':                     ('VT - State Government',                      CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-state-house-of-representatives':       ('VT - State House of Representatives',        CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-state-officers':                       ('VT - State Officers',                        CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-state-senate':                         ('VT - State Senate',                          CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-trailer-dealer':                       ('VT - Trailer Dealer',                        CAT['Dealer / Manufacturer'],        90, 'Trailer',    VT_SPECIALTY),
        'vt-trailer-heavy':                        ('VT - Trailer - Heavy',                       CAT['Government / Exempt'],          88, 'Trailer',    VT_SPECIALTY),
        'vt-trailer-light':                        ('VT - Trailer - Light',                       CAT['Government / Exempt'],          88, 'Trailer',    VT_SPECIALTY),
        'vt-transporter':                          ('VT - Transporter',                           CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-truck':                                ('VT - Truck',                                 CAT['Government / Exempt'],          88, 'Commercial', VT_SPECIALTY),
        'vt-us-house':                             ('VT - US House',                              CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-us-senate':                            ('VT - US Senate',                             CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-vermont-house-speaker':                ('VT - Vermont House Speaker',                 CAT['Government / Exempt'],          90, 'Passenger',  VT_SPECIALTY),
        'vt-volunteer':                            ('VT - Volunteer',                             CAT['Other / Specialty'],            88, 'Passenger',  VT_SPECIALTY),
        # ── vt-outdoor → 840 ─────────────────────────────────────────────────
        'vt-conservation-deer':                ('VT - Conservation - Deer',                       CAT['Conservation / Environment'],   90, 'Passenger',  VT_SPECIALTY),
        'vt-conservation-deer-truck':          ('VT - Conservation - Deer - Truck',               CAT['Conservation / Environment'],   90, 'Commercial', VT_SPECIALTY),
        'vt-conservation-loon':                ('VT - Conservation - Loon',                       CAT['Conservation / Environment'],   90, 'Passenger',  VT_SPECIALTY),
        'vt-conservation-loon-truck':          ('VT - Conservation - Loon - Truck',               CAT['Conservation / Environment'],   90, 'Commercial', VT_SPECIALTY),
        'vt-conservation-trout':               ('VT - Conservation - Trout',                      CAT['Conservation / Environment'],   90, 'Passenger',  VT_SPECIALTY),
        'vt-conservation-trout-truck':         ('VT - Conservation - Trout - Truck',              CAT['Conservation / Environment'],   90, 'Commercial', VT_SPECIALTY),
        # ── vt-specialty → 840 ───────────────────────────────────────────────
        'vt-building-bright-futures':          ('VT - Building Bright Futures',                   CAT['Other / Specialty'],            88, 'Passenger',  VT_SPECIALTY),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class, series = NAME_OVERRIDE[stem]

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     46,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_va(stem: str, subfolder: str, actual_filename: str):
    """Virginia plates — multi-subfolder layout (region 47)."""
    CATCH = VA_SPECIALTY  # 848 — schools, military, outdoors, sports, fraternal, first-responder, specialty

    NAME_OVERRIDE = {
        # ── va-standard-issue ──────────────────────────────────────────────
        'va-amateur-radio':                       ('VA - Amateur Radio',                               CAT['Radio / Amateur Radio'],        95, 'Passenger',   VA_STD_SERIES),
        'va-antique-veh-black-bkground':          ('VA - Antique - Black',                             CAT['Historical / Commemorative'],   88, 'Passenger',   VA_STD_SERIES),
        'va-antique-veh-yellow-bkground':         ('VA - Antique - Yellow',                            CAT['Historical / Commemorative'],   88, 'Passenger',   VA_STD_SERIES),
        'va-great-seal':                          ('VA - Great Seal',                                  CAT['Government / Exempt'],          90, 'Passenger',   VA_STD_SERIES),
        'va-great-seal-motorcycle':               ('VA - Great Seal - Motorcycle',                     CAT['Government / Exempt'],          90, 'Motorcycle',  VA_STD_SERIES),
        'va-moped':                               ('VA - Moped',                                       CAT['Standard Issue'],               88, 'Motorcycle',  VA_STD_SERIES),
        'va-motorcycle':                          ('VA - Motorcycle',                                  CAT['Standard Issue'],               95, 'Motorcycle',  VA_STD_SERIES),
        'va-motorcycle-antique-blk-wht':          ('VA - Motorcycle Antique - Black and White',        CAT['Historical / Commemorative'],   88, 'Motorcycle',  VA_STD_SERIES),
        'va-motorcycle-antique-yellow':           ('VA - Motorcycle Antique - Yellow',                 CAT['Historical / Commemorative'],   88, 'Motorcycle',  VA_STD_SERIES),
        'va-standard-issue-2014':                 ('VA - Standard Issue - 2014',                       CAT['Standard Issue'],               95, 'Passenger',   VA_STD_SERIES),
        'va-standard-issue-2014-personalized':    ('VA - Standard Issue - 2014 - Personalized',        CAT['Standard Issue'],               88, 'Passenger',   VA_STD_SERIES),
        # ── va-non-passenger-and-government ───────────────────────────────
        'va-apportioned-irp':                     ('VA - Apportioned IRP',                             CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-apportioned-permanent-irp':           ('VA - Apportioned Permanent IRP',                   CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-clean-special-fuel-for-hire':         ('VA - Clean Special Fuel - For Hire',               CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-equipment':                           ('VA - Equipment',                                   CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-farm-vehicle':                        ('VA - Farm Vehicle',                                CAT['Agricultural'],                 88, 'Commercial',  VA_NONPASS_SERIES),
        'va-farm-vehicle-permanent':              ('VA - Farm Vehicle - Permanent',                    CAT['Agricultural'],                 88, 'Commercial',  VA_NONPASS_SERIES),
        'va-great-seal-for-hire':                 ('VA - Great Seal - For Hire',                       CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-low-speed-standard-plate':            ('VA - Low Speed Vehicle',                           CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-military-surplus-vehicle':            ('VA - Military Surplus Vehicle',                    CAT['Military / Veteran'],           88, 'Commercial',  VA_NONPASS_SERIES),
        'va-non-apportioned-bus':                 ('VA - Non-Apportioned Bus',                         CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-nonemergency-medical-transport-for-hire': ('VA - Non-Emergency Medical Transport - For Hire', CAT['Government / Exempt'],       88, 'Commercial',  VA_NONPASS_SERIES),
        'va-passenger-for-hire':                  ('VA - Passenger - For Hire',                        CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-scenic-for-hire':                     ('VA - Scenic - For Hire',                           CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-taxi-for-hire':                       ('VA - Taxi - For Hire',                             CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-taxi-permanent-for-hire':             ('VA - Taxi - Permanent - For Hire',                 CAT['Government / Exempt'],          88, 'Passenger',   VA_NONPASS_SERIES),
        'va-tow-truck-for-hire':                  ('VA - Tow Truck - For Hire',                        CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-tow-truck-for-hire-permanent':        ('VA - Tow Truck - For Hire - Permanent',            CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-tractor-permanent-private-for-hire':  ('VA - Tractor - Permanent - Private or For Hire',   CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-tractor-private-or-for-hire':         ('VA - Tractor - Private or For Hire',               CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-trailer':                             ('VA - Trailer',                                     CAT['Government / Exempt'],          88, 'Trailer',     VA_NONPASS_SERIES),
        'va-trailer-permanent':                   ('VA - Trailer - Permanent',                         CAT['Government / Exempt'],          88, 'Trailer',     VA_NONPASS_SERIES),
        'va-trailer-rental':                      ('VA - Trailer - Rental',                            CAT['Government / Exempt'],          88, 'Trailer',     VA_NONPASS_SERIES),
        'va-trailer-small-permanent':             ('VA - Trailer - Small Permanent',                   CAT['Government / Exempt'],          88, 'Trailer',     VA_NONPASS_SERIES),
        'va-truck-permanent-private-or-for-hire': ('VA - Truck - Permanent - Private or For Hire',     CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-truck-private-or-for-hire':           ('VA - Truck - Private or For Hire',                 CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-truck-tractor-rental':                ('VA - Truck Tractor - Rental',                      CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        'va-truck-tractor-rental-permanent':      ('VA - Truck Tractor - Rental - Permanent',          CAT['Government / Exempt'],          88, 'Commercial',  VA_NONPASS_SERIES),
        # ── va-first-responder ─────────────────────────────────────────────
        'va-firefighter-volunteer':               ('VA - Firefighter - Volunteer',                     CAT['First Responder'],              90, 'Passenger',   CATCH),
        'va-firefighter-volunteer-motorcycle':    ('VA - Firefighter - Volunteer - Motorcycle',        CAT['First Responder'],              90, 'Motorcycle',  CATCH),
        'va-law-officers-mem-motorcycle':         ('VA - Law Officers Memorial - Motorcycle',          CAT['First Responder'],              88, 'Motorcycle',  CATCH),
        'va-law-officers-memorial-v1':            ('VA - Law Officers Memorial - V1',                  CAT['First Responder'],              88, 'Passenger',   CATCH),
        'va-law-officers-memorial-v2':            ('VA - Law Officers Memorial - V2',                  CAT['First Responder'],              88, 'Passenger',   CATCH),
        'va-order-of-police':                     ('VA - Order of Police',                             CAT['First Responder'],              90, 'Passenger',   CATCH),
        'va-order-of-police-motorcycle':          ('VA - Order of Police - Motorcycle',                CAT['First Responder'],              90, 'Motorcycle',  CATCH),
        'va-professional-firefighter-int-l':      ("VA - Professional Firefighter Int'l",              CAT['First Responder'],              88, 'Passenger',   CATCH),
        'va-professional-firefighter-int-l-motorcycle': ("VA - Professional Firefighter Int'l - Motorcycle", CAT['First Responder'],       88, 'Motorcycle',  CATCH),
        'va-rescue-squad':                        ('VA - Rescue Squad',                                CAT['First Responder'],              90, 'Passenger',   CATCH),
        # ── va-fratrnal ────────────────────────────────────────────────────
        'va-alpha-kappa-alpha':                   ('VA - Alpha Kappa Alpha',                           CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-alpha-phi-alpha':                     ('VA - Alpha Phi Alpha',                             CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-delta-sigma-theta':                   ('VA - Delta Sigma Theta',                           CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-freemason':                           ('VA - Freemason',                                   CAT['Fraternal / Civic'],            90, 'Passenger',   CATCH),
        'va-kappa-alpha-psi':                     ('VA - Kappa Alpha Psi',                             CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-knights-of-columbus':                 ('VA - Knights of Columbus',                         CAT['Fraternal / Civic'],            90, 'Passenger',   CATCH),
        'va-lions-of-virginia':                   ('VA - Lions of Virginia',                           CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-masons-prince-hall':                  ('VA - Masons - Prince Hall',                        CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-omega-psi-phi':                       ('VA - Omega Psi Phi',                               CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-order-of-the-eastern-star':           ('VA - Order of the Eastern Star',                   CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-phi-beta-sigma':                      ('VA - Phi Beta Sigma',                              CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-rotary-international':                ('VA - Rotary International',                        CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-shriner':                             ('VA - Shriner',                                     CAT['Fraternal / Civic'],            90, 'Passenger',   CATCH),
        'va-zeta-phi-beta':                       ('VA - Zeta Phi Beta',                               CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        # ── va-military ────────────────────────────────────────────────────
        'va-173rd-airborne':                      ('VA - 173rd Airborne',                              CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-air-force-cross':                     ('VA - Air Force Cross',                             CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-air-force-reserve':                   ('VA - US Air Force Reserve',                        CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-air-medal':                           ('VA - Air Medal',                                   CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-air-medal-motorcycle':                ('VA - Air Medal - Motorcycle',                      CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-armed-forces-expeditionary-medal':    ('VA - Armed Forces Expeditionary Medal',            CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-army':                                ('VA - US Army',                                     CAT['Military / Veteran'],           95, 'Passenger',   CATCH),
        'va-army-motorcycle':                     ('VA - US Army - Motorcycle',                        CAT['Military / Veteran'],           95, 'Motorcycle',  CATCH),
        'va-army-reserve':                        ('VA - US Army Reserve',                             CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-bronze-star':                         ('VA - Bronze Star',                                 CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-bronze-star-awards-multiple':         ('VA - Bronze Star - Awards Multiple',               CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-bronze-star-motorcycle':              ('VA - Bronze Star - Motorcycle',                    CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-bronze-star-motorcycle-awards-multiple': ('VA - Bronze Star - Motorcycle - Awards Multiple', CAT['Military / Veteran'],         88, 'Motorcycle',  CATCH),
        'va-bronze-star-valor':                   ('VA - Bronze Star - Valor',                         CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-chosin-reservoir-survivor':           ('VA - Chosin Reservoir Survivor',                   CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-coast-guard':                         ('VA - US Coast Guard',                              CAT['Military / Veteran'],           95, 'Passenger',   CATCH),
        'va-coast-guard-reserve':                 ('VA - US Coast Guard Reserve',                      CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-combat-infantryman':                  ('VA - Combat Infantryman',                          CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-desert-shield-storm-veteran':         ('VA - Desert Shield - Storm Veteran',               CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-desert-shield-storm-veteran-motorcycle': ('VA - Desert Shield - Storm Veteran - Motorcycle', CAT['Military / Veteran'],         88, 'Motorcycle',  CATCH),
        'va-disabled-veteran':                    ('VA - Disabled Veteran',                            CAT['Military / Veteran'],           95, 'Passenger',   CATCH),
        'va-disabled-veteran-motorcycle':         ('VA - Disabled Veteran - Motorcycle',               CAT['Military / Veteran'],           95, 'Motorcycle',  CATCH),
        'va-distinguished-flying-cross':          ('VA - Distinguished Flying Cross',                  CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-distinguished-service-cross':         ('VA - Distinguished Service Cross',                 CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-enduring-freedom-veteran':            ('VA - Enduring Freedom Veteran',                    CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-former-prisoner-of-war':              ('VA - Former Prisoner of War',                      CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-gold-star':                           ('VA - Gold Star Family',                            CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-gold-star-motorcycle':                ('VA - Gold Star Family - Motorcycle',               CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-iraqi-freedom-veteran':               ('VA - Iraqi Freedom Veteran',                       CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-iraqi-freedom-veteran-motorcycle':    ('VA - Iraqi Freedom Veteran - Motorcycle',          CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-korean-war-veteran':                  ('VA - Korean War Veteran',                          CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-legion-of-merit':                     ('VA - Legion of Merit',                             CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-legion-of-merit-awards-multiple':     ('VA - Legion of Merit - Awards Multiple',           CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-legion-of-valor-of-the-usa':          ('VA - Legion of Valor of the USA',                  CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-marine-corps-league':                 ('VA - Marine Corps League',                         CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-marine-corps-motorcycle':             ('VA - US Marine Corps - Motorcycle',                CAT['Military / Veteran'],           95, 'Motorcycle',  CATCH),
        'va-marine-corps-reserve':                ('VA - US Marine Corps Reserve',                     CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-marine-corps-semper-fidelis':         ('VA - US Marine Corps - Semper Fidelis',            CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-national-guard':                      ('VA - Virginia National Guard',                     CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-national-guard-retired':              ('VA - Virginia National Guard - Retired',           CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-naval-aviator':                       ('VA - Naval Aviator',                               CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-navy-cross':                          ('VA - Navy Cross',                                  CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-navy-marine-corps-medal':             ('VA - Navy and Marine Corps Medal',                 CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-navy-reserve':                        ('VA - US Navy Reserve',                             CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-navy-u-s':                            ('VA - US Navy',                                     CAT['Military / Veteran'],           95, 'Passenger',   CATCH),
        'va-navy-us-motorcycle':                  ('VA - US Navy - Motorcycle',                        CAT['Military / Veteran'],           95, 'Motorcycle',  CATCH),
        'va-next-of-kin':                         ('VA - Next of Kin',                                 CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-pearl-harbor-survivor':               ('VA - Pearl Harbor Survivor',                       CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-purple-heart':                        ('VA - Purple Heart',                                CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-purple-heart-awards-multiple':        ('VA - Purple Heart - Awards Multiple',              CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-purple-heart-motorcyle':              ('VA - Purple Heart - Motorcycle',                   CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-purple-heart-motorcyle-awards-multiple': ('VA - Purple Heart - Motorcycle - Awards Multiple', CAT['Military / Veteran'],        88, 'Motorcycle',  CATCH),
        'va-silver-star':                         ('VA - Silver Star',                                 CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-silver-star-motorcycle':              ('VA - Silver Star - Motorcycle',                    CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-special-forces-association':          ('VA - Special Forces Association',                  CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-us-3rd-infantry-regiment':            ('VA - US 3rd Infantry Regiment',                    CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-uss-cole':                            ('VA - USS Cole',                                    CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-veteran-armed-forces':                ('VA - Veteran - Armed Forces',                      CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-veteran-armed-forces-motorcycle':     ('VA - Veteran - Armed Forces - Motorcycle',         CAT['Military / Veteran'],           88, 'Motorcycle',  CATCH),
        'va-veterans-of-foreign-wars':            ('VA - Veterans of Foreign Wars',                    CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-vietnam-veteran':                     ('VA - Vietnam Veteran',                             CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-vietnam-veterans-of-america':         ('VA - Vietnam Veterans of America',                 CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-virginia-defense-force':              ('VA - Virginia Defense Force',                      CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-world-war-ii-veteran':                ('VA - World War II Veteran',                        CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        # ── va-outdoors ────────────────────────────────────────────────────
        'va-appalachian-trail':                   ('VA - Appalachian Trail',                           CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-bicycle-enthusiasts':                 ('VA - Bicycle Enthusiasts',                         CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-blue-ridge-parkway-foundation':       ('VA - Blue Ridge Parkway Foundation',               CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-blue-ridge-parkway-foundation-motorcycle': ('VA - Blue Ridge Parkway Foundation - Motorcycle', CAT['Conservation / Environment'], 88, 'Motorcycle', CATCH),
        'va-boat-us':                             ('VA - Boat US',                                     CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-butterfly-heritage':                  ('VA - Butterfly Heritage',                          CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-chesapeake-bay':                      ('VA - Chesapeake Bay',                              CAT['Conservation / Environment'],   90, 'Passenger',   CATCH),
        'va-ducks-unlimited':                     ('VA - Ducks Unlimited',                             CAT['Conservation / Environment'],   90, 'Passenger',   CATCH),
        'va-eastern-shore':                       ('VA - Eastern Shore',                               CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-fox-hunting-license-plate':           ('VA - Fox Hunting',                                 CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-friends-of-the-blue-ridge':           ('VA - Friends of the Blue Ridge',                   CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-heritage-state-bird':                 ('VA - Heritage - State Bird',                       CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-heritage-state-bird-motorcycle':      ('VA - Heritage - State Bird - Motorcycle',          CAT['Conservation / Environment'],   88, 'Motorcycle',  CATCH),
        'va-horse-enthusiasts':                   ('VA - Horse Enthusiasts',                           CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-horse-enthusiasts-motorcycle':        ('VA - Horse Enthusiasts - Motorcycle',              CAT['Conservation / Environment'],   88, 'Motorcycle',  CATCH),
        'va-james-river-park-system':             ('VA - James River Park System',                     CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-james-river-park-system-motorcycle':  ('VA - James River Park System - Motorcycle',        CAT['Conservation / Environment'],   88, 'Motorcycle',  CATCH),
        'va-lighthouses-virginia':                ('VA - Lighthouses of Virginia',                     CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-natural-bridge':                      ('VA - Natural Bridge',                              CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-northern-neck':                       ('VA - Northern Neck',                               CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-protect-pollinators':                 ('VA - Protect Pollinators',                         CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-protect-sea-life':                    ('VA - Protect Sea Life',                            CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-scenic-autumn':                       ('VA - Scenic - Autumn',                             CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-scenic-mountain-to-seashore':         ('VA - Scenic - Mountain to Seashore',               CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-shenandoah-national-park':            ('VA - Shenandoah National Park',                    CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-shenandoah-national-park-motorcycle': ('VA - Shenandoah National Park - Motorcycle',       CAT['Conservation / Environment'],   88, 'Motorcycle',  CATCH),
        'va-smith-mountain-lake':                 ('VA - Smith Mountain Lake',                         CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-virginia-agriculture':                ('VA - Virginia Agriculture',                        CAT['Agricultural'],                 88, 'Passenger',   CATCH),
        'va-virginia-state-parks':                ('VA - Virginia State Parks',                        CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildflower':                          ('VA - Wildflower',                                  CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-bass':                       ('VA - Wildlife - Bass',                             CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-bear':                       ('VA - Wildlife - Bear',                             CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-bluebird':                   ('VA - Wildlife - Bluebird',                         CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-brook-trout':                ('VA - Wildlife - Brook Trout',                      CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-eagle':                      ('VA - Wildlife - Eagle',                            CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-mallard':                    ('VA - Wildlife - Mallard',                          CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-red-salamander':             ('VA - Wildlife - Red Salamander',                   CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-turkey':                     ('VA - Wildlife - Turkey',                           CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-wildlife-whitetail-deer':             ('VA - Wildlife - Whitetail Deer',                   CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        # ── va-schools ─────────────────────────────────────────────────────
        'va-american-national-university':        ('VA - American National University',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-auburn-university':                   ('VA - Auburn University',                           CAT['School'],                       88, 'Passenger',   CATCH),
        'va-averett-university':                  ('VA - Averett University',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-bluefield-university':                ('VA - Bluefield University',                        CAT['School'],                       88, 'Passenger',   CATCH),
        'va-blue-ridge-community-college':        ('VA - Blue Ridge Community College',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-bridgewater-college':                 ('VA - Bridgewater College',                         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-christopher-newport-university':      ('VA - Christopher Newport University',              CAT['School'],                       88, 'Passenger',   CATCH),
        'va-citadel-university':                  ('VA - The Citadel',                                 CAT['School'],                       88, 'Passenger',   CATCH),
        'va-clemson-university':                  ('VA - Clemson University',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-danville-community-college':          ('VA - Danville Community College',                  CAT['School'],                       88, 'Passenger',   CATCH),
        'va-duke-university':                     ('VA - Duke University',                             CAT['School'],                       88, 'Passenger',   CATCH),
        'va-east-carolina-university':            ('VA - East Carolina University',                    CAT['School'],                       88, 'Passenger',   CATCH),
        'va-eastern-mennonite-university':        ('VA - Eastern Mennonite University',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-eastern-virginia-med-school':         ('VA - Eastern Virginia Medical School',             CAT['School'],                       88, 'Passenger',   CATCH),
        'va-emory-henry-college':                 ('VA - Emory and Henry College',                     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-ferrum-college':                      ('VA - Ferrum College',                              CAT['School'],                       88, 'Passenger',   CATCH),
        'va-florida-state-university':            ('VA - Florida State University',                    CAT['School'],                       88, 'Passenger',   CATCH),
        'va-george-mason-university':             ('VA - George Mason University',                     CAT['School'],                       90, 'Passenger',   CATCH),
        'va-george-mason-university-patriots':    ('VA - George Mason University - Patriots',          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-george-mason-university-patriots-v2': ('VA - George Mason University - Patriots - V2',     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-george-mason-university-v2':          ('VA - George Mason University - V2',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-georgetown-university':               ('VA - Georgetown University',                       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-george-washington-university':        ('VA - George Washington University',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-georgia-tech':                        ('VA - Georgia Tech',                                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-germanna-community-college':          ('VA - Germanna Community College',                  CAT['School'],                       88, 'Passenger',   CATCH),
        'va-hampden-sydney-college':              ('VA - Hampden-Sydney College',                      CAT['School'],                       88, 'Passenger',   CATCH),
        'va-hampton-university':                  ('VA - Hampton University',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-hollins-university':                  ('VA - Hollins University',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-james-madison-university-athletic':   ('VA - James Madison University - Athletic',         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-james-madison-university-seal':       ('VA - James Madison University - Seal',             CAT['School'],                       88, 'Passenger',   CATCH),
        'va-jefferson-college-of-health-sci':     ('VA - Jefferson College of Health Sciences',        CAT['School'],                       88, 'Passenger',   CATCH),
        'va-j-sargeant-reynolds-community':       ('VA - J. Sargeant Reynolds Community College',      CAT['School'],                       88, 'Passenger',   CATCH),
        'va-liberty-university':                  ('VA - Liberty University',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-longwood-university':                 ('VA - Longwood University',                         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-lynchburg-college':                   ('VA - Lynchburg College',                           CAT['School'],                       88, 'Passenger',   CATCH),
        'va-marshall-university':                 ('VA - Marshall University',                         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-mary-baldwin-university':             ('VA - Mary Baldwin University',                     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-marymount-university':                ('VA - Marymount University',                        CAT['School'],                       88, 'Passenger',   CATCH),
        'va-mountain-empire-community-coll':      ('VA - Mountain Empire Community College',           CAT['School'],                       88, 'Passenger',   CATCH),
        'va-nc-state-university':                 ('VA - NC State University',                         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-newport-news-shipbuilding':           ('VA - Newport News Shipbuilding',                   CAT['School'],                       88, 'Passenger',   CATCH),
        'va-norfolk-state-university':            ('VA - Norfolk State University',                    CAT['School'],                       88, 'Passenger',   CATCH),
        'va-norfolk-state-university-tower':      ('VA - Norfolk State University - Tower',            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-northern-virginia-community-college': ('VA - Northern Virginia Community College',         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-ohio-state-university':               ('VA - Ohio State University',                       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-old-dominion-university':             ('VA - Old Dominion University',                     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-paul-d-camp-community-college':       ('VA - Paul D. Camp Community College',              CAT['School'],                       88, 'Passenger',   CATCH),
        'va-penn-state-university':               ('VA - Penn State University',                       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-piedmont-virginia-community-college': ('VA - Piedmont Virginia Community College',         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-radford-university':                  ('VA - Radford University',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-radford-university-highlanders':      ('VA - Radford University - Highlanders',            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-radford-university-v2':               ('VA - Radford University - V2',                     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-randolph-college':                    ('VA - Randolph College',                            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-randolph-macon-college-school-seal':  ('VA - Randolph-Macon College - School Seal',        CAT['School'],                       88, 'Passenger',   CATCH),
        'va-randolph-macon-college-yellow-jack':  ('VA - Randolph-Macon College - Yellow Jacket',      CAT['School'],                       88, 'Passenger',   CATCH),
        'va-randolph-macon-college-yellow-jack-v2': ('VA - Randolph-Macon College - Yellow Jacket - V2', CAT['School'],                     88, 'Passenger',   CATCH),
        'va-regent-university':                   ('VA - Regent University',                           CAT['School'],                       88, 'Passenger',   CATCH),
        'va-roanoke-college':                     ('VA - Roanoke College',                             CAT['School'],                       88, 'Passenger',   CATCH),
        'va-sentara-college-of-health-sciences':  ('VA - Sentara College of Health Sciences',          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-shenandoah-university':               ('VA - Shenandoah University',                       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-southwest-virginia-community-college': ('VA - Southwest Virginia Community College',       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-sweet-briar-college':                 ('VA - Sweet Briar College',                         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-texas-a-m-university':                ('VA - Texas A&M University',                        CAT['School'],                       88, 'Passenger',   CATCH),
        'va-tidewater-community-college':         ('VA - Tidewater Community College',                 CAT['School'],                       88, 'Passenger',   CATCH),
        'va-unc-tar-heels':                       ('VA - UNC Tar Heels',                               CAT['School'],                       88, 'Passenger',   CATCH),
        'va-united-states-air-force-academy':     ('VA - US Air Force Academy',                        CAT['School'],                       88, 'Passenger',   CATCH),
        'va-united-states-air-force-academy-motorcycle': ('VA - US Air Force Academy - Motorcycle',    CAT['School'],                       88, 'Motorcycle',  CATCH),
        'va-united-states-military-academy':      ('VA - US Military Academy',                         CAT['School'],                       88, 'Passenger',   CATCH),
        'va-united-states-naval-academy':         ('VA - US Naval Academy',                            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-florida':               ('VA - University of Florida',                       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-maryland':              ('VA - University of Maryland',                      CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-mary-washington':       ('VA - University of Mary Washington',               CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-michigan':              ('VA - University of Michigan',                      CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-notre-dame':            ('VA - University of Notre Dame',                    CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-richmond-crest':        ('VA - University of Richmond - Crest',              CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-richmond-spider':       ('VA - University of Richmond - Spider',             CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-south-carolina':        ('VA - University of South Carolina',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-tennessee':             ('VA - University of Tennessee',                     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-virginia':              ('VA - University of Virginia',                      CAT['School'],                       90, 'Passenger',   CATCH),
        'va-university-of-virginia-rotunda':      ('VA - University of Virginia - Rotunda',            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-virginia-sabre':        ('VA - University of Virginia - Sabre',              CAT['School'],                       88, 'Passenger',   CATCH),
        'va-university-of-virginia-wise':         ('VA - University of Virginia - Wise',               CAT['School'],                       88, 'Passenger',   CATCH),
        'va-unlocking-autism':                    ('VA - Unlocking Autism',                            CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-virginia-commonwealth-ram':           ('VA - Virginia Commonwealth University - Ram',      CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-commonwealth-ram-v2':        ('VA - Virginia Commonwealth University - Ram - V2', CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-commonwealth-seal':          ('VA - Virginia Commonwealth University - Seal',     CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-highlands-community-college': ('VA - Virginia Highlands Community College',       CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-military-insitute':          ('VA - Virginia Military Institute',                 CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-state-university-seal':      ('VA - Virginia State University - Seal',            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-state-university-trojan':    ('VA - Virginia State University - Trojan',          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-tech-go-hokies':             ('VA - Virginia Tech - Go Hokies',                   CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-tech-hokie-bird':            ('VA - Virginia Tech - Hokie Bird',                  CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-tech-mountains':             ('VA - Virginia Tech - Mountains',                   CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-tech-school-seal':           ('VA - Virginia Tech - School Seal',                 CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-tech-vt':                    ('VA - Virginia Tech - VT',                          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-union-university':           ('VA - Virginia Union University',                   CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-wesleyan-university':        ('VA - Virginia Wesleyan University',                CAT['School'],                       88, 'Passenger',   CATCH),
        'va-virginia-western-community-college':  ('VA - Virginia Western Community College',          CAT['School'],                       88, 'Passenger',   CATCH),
        'va-washington-lee-university':           ('VA - Washington and Lee University',               CAT['School'],                       88, 'Passenger',   CATCH),
        'va-west-virginia-university':            ('VA - West Virginia University',                    CAT['School'],                       88, 'Passenger',   CATCH),
        'va-william-mary':                        ('VA - William and Mary',                            CAT['School'],                       88, 'Passenger',   CATCH),
        'va-william-mary-athletic':               ('VA - William and Mary - Athletic',                 CAT['School'],                       88, 'Passenger',   CATCH),
        'va-wytheville-community-college':        ('VA - Wytheville Community College',                CAT['School'],                       88, 'Passenger',   CATCH),
        # ── va-sports ──────────────────────────────────────────────────────
        'va-washington-capitals':                 ('VA - Washington Capitals',                         CAT['Sports Team'],                  90, 'Passenger',   CATCH),
        'va-washington-nationals':                ('VA - Washington Nationals',                        CAT['Sports Team'],                  90, 'Passenger',   CATCH),
        'va-washington-nationals-motorcycle':     ('VA - Washington Nationals - Motorcycle',           CAT['Sports Team'],                  90, 'Motorcycle',  CATCH),
        # ── va-specialty ───────────────────────────────────────────────────
        'va-250-anniversary':                     ('VA - 250th Anniversary',                           CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-afl-cio':                             ('VA - AFL-CIO',                                     CAT['Fraternal / Civic'],            88, 'Passenger',   CATCH),
        'va-alzheimers-association':              ('VA - Alzheimers Association',                      CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-alzheimers-association-motorcycle':   ('VA - Alzheimers Association - Motorcycle',         CAT['Health & Awareness'],           88, 'Motorcycle',  CATCH),
        'va-animal-friendly':                     ('VA - Animal Friendly',                             CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-aviation-enthusiasts':                ('VA - Aviation Enthusiasts',                        CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-bowler':                              ('VA - Bowler',                                      CAT['Sports Team'],                  88, 'Passenger',   CATCH),
        'va-chesapeake-city':                     ('VA - Chesapeake City',                             CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-choose-life':                         ('VA - Choose Life',                                 CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-class-j-no-611-steam-locomotv':       ('VA - Class J No 611 Steam Locomotive',             CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-clean-special-fuel':                  ('VA - Clean Special Fuel',                          CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-colonial-williamsburg':               ('VA - Colonial Williamsburg',                       CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-community-peacebuilding':             ('VA - Community Peacebuilding',                     CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-cure-childhood-cancer':               ('VA - Cure Childhood Cancer',                       CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-cure-childhood-cancer-motorcycle':    ('VA - Cure Childhood Cancer - Motorcycle',          CAT['Health & Awareness'],           88, 'Motorcycle',  CATCH),
        'va-diabetes':                            ('VA - Diabetes',                                    CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-don-t-tread-on-me':                   ("VA - Don't Tread on Me",                           CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-don-t-tread-on-me-motorcycle':        ("VA - Don't Tread on Me - Motorcycle",              CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-don-t-tread-on-me-truck':             ("VA - Don't Tread on Me - Truck",                   CAT['Other / Specialty'],            88, 'Commercial',  CATCH),
        'va-drive-smart':                         ('VA - Drive Smart',                                 CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-eyes-on-the-road':                    ('VA - Eyes on the Road',                            CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-fairfax-city':                        ('VA - Fairfax City',                                CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-family-children-fund-hand':           ('VA - Family and Children Fund - Hand',             CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-family-children-fund-heart':          ('VA - Family and Children Fund - Heart',            CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-family-children-fund-kids-1st':       ('VA - Family and Children Fund - Kids 1st',         CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-family-children-fund-star':           ('VA - Family and Children Fund - Star',             CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-ffa-future-farmers-of-america':       ('VA - FFA - Future Farmers of America',             CAT['Agricultural'],                 88, 'Passenger',   CATCH),
        'va-fight-terrorism':                     ('VA - Fight Terrorism',                             CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-fight-terrorism-motorcycle':          ('VA - Fight Terrorism - Motorcycle',                CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-friends-of-coal':                     ('VA - Friends of Coal',                             CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-friends-of-coal-motorcycle':          ('VA - Friends of Coal - Motorcycle',                CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-friends-of-tibet':                    ('VA - Friends of Tibet',                            CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-greyhound-adopt':                     ('VA - Greyhound Adopt',                             CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-harley-davidson-owners-group':        ('VA - Harley-Davidson Owners Group',                CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-harley-owners-group-motorcycle':      ('VA - Harley-Davidson Owners Group - Motorcycle',   CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-home-education':                      ('VA - Home Education',                              CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-in-god-we-trust':                     ('VA - In God We Trust',                             CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-in-god-we-trust-motorcycle':          ('VA - In God We Trust - Motorcycle',                CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-internet-capital':                    ('VA - Internet Capital',                            CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-keeping-the-lights-on':               ('VA - Keeping the Lights On',                       CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-keeping-the-lights-on-motorcycle':    ('VA - Keeping the Lights On - Motorcycle',          CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-megs-miles':                          ("VA - Meg's Miles",                                 CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-move-over':                           ('VA - Move Over',                                   CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-nasa-langley-research-center':        ('VA - NASA Langley Research Center',                CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-nasa-wallops-flight-facility':        ('VA - NASA Wallops Flight Facility',                CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-national-air-and-space-museum':       ('VA - National Air and Space Museum',               CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-national-rifle-association':          ('VA - National Rifle Association',                  CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-newport-news-shipbuilding-motorcycle': ('VA - Newport News Shipbuilding - Motorcycle',     CAT['School'],                       88, 'Motorcycle',  CATCH),
        'va-nurses-foundation':                   ('VA - Nurses Foundation',                           CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-oceana-naval-air-station':            ('VA - Oceana Naval Air Station',                    CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-organ-donor':                         ('VA - Organ Donor',                                 CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-organ-donor-motorcycle':              ('VA - Organ Donor - Motorcycle',                    CAT['Health & Awareness'],           88, 'Motorcycle',  CATCH),
        'va-parrothead':                          ('VA - Parrothead',                                  CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-parrothead-motorcycle':               ('VA - Parrothead - Motorcycle',                     CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-peace':                               ('VA - Peace',                                       CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-peace-begins-at-home':                ('VA - Peace Begins at Home',                        CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-poquoson-city':                       ('VA - Poquoson City',                               CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-richmond-planet':                     ('VA - Richmond Planet',                             CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-richmond-planet-motorcycle':          ('VA - Richmond Planet - Motorcycle',                CAT['Historical / Commemorative'],   88, 'Motorcycle',  CATCH),
        'va-robert-e-lee':                        ('VA - Robert E Lee',                                CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-scenic-motorcycle':                   ('VA - Scenic - Motorcycle',                         CAT['Conservation / Environment'],   88, 'Motorcycle',  CATCH),
        'va-scenic-patriot':                      ('VA - Scenic - Patriot',                            CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-sons-of-confederate-veterans':        ('VA - Sons of Confederate Veterans',                CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-sons-of-confederate-veterans-motorcycle': ('VA - Sons of Confederate Veterans - Motorcycle', CAT['Historical / Commemorative'], 88, 'Motorcycle',  CATCH),
        'va-stop-gun-violence':                   ('VA - Stop Gun Violence',                           CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-support-our-troops':                  ('VA - Support Our Troops',                          CAT['Military / Veteran'],           88, 'Passenger',   CATCH),
        'va-surfrider-foundation':                ('VA - Surfrider Foundation',                        CAT['Conservation / Environment'],   88, 'Passenger',   CATCH),
        'va-teamtommie':                          ('VA - Team Tommie',                                 CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-tobacco-heritage':                    ('VA - Tobacco Heritage',                            CAT['Historical / Commemorative'],   88, 'Passenger',   CATCH),
        'va-tobacco-heritage-truck':              ('VA - Tobacco Heritage - Truck',                    CAT['Historical / Commemorative'],   88, 'Commercial',  CATCH),
        'va-trust-women-respect-choice':          ('VA - Trust Women Respect Choice',                  CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-united-we-stand':                     ('VA - United We Stand',                             CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-united-we-stand-motorcycle':          ('VA - United We Stand - Motorcycle',                CAT['Other / Specialty'],            88, 'Motorcycle',  CATCH),
        'va-virginia-beach-city':                 ('VA - Virginia Beach City',                         CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
        'va-virginia-breast-cancer-foundation':   ('VA - Virginia Breast Cancer Foundation',           CAT['Health & Awareness'],           88, 'Passenger',   CATCH),
        'va-virginia-for-the-arts':               ('VA - Virginia for the Arts',                       CAT['Arts / Culture'],               88, 'Passenger',   CATCH),
        'va-virginians-for-the-arts':             ('VA - Virginians for the Arts',                     CAT['Arts / Culture'],               88, 'Passenger',   CATCH),
        'va-virginia-realtors':                   ('VA - Virginia Realtors',                           CAT['Other / Specialty'],            88, 'Passenger',   CATCH),
    }

    hit = NAME_OVERRIDE.get(stem)
    if hit is None:
        return None
    plate_name, cat_id, cat_conf, veh_class, series = hit
    return {
        'filename':        actual_filename,
        'plate_name':      plate_name,
        'slug':            slug_from_name(plate_name),
        'category_id':     cat_id,
        'category_conf':   cat_conf,
        'vehicle_class':   veh_class,
        'series_id':       series['id'],
        'series_conf':     series['conf'],
        'region_id':       47,
        'notes':           [],
        'src_subfolder':   subfolder,
    }


def parse_wi(stem: str, subfolder: str, actual_filename: str):
    """Parse a single WI (Wisconsin) plate image from multi-subfolder structure.

    Series routing:
      841 (Standard Issue)          — wi-standard-issue, EXCEPT blackout/retro-yellow
      842 (Alternative Series)      — wi-blackout, wi-retro-yellow
      843 (Non-passenger/Govt)      — wi-non-passenger-government (catch-all)
      844 (Tribal Nations)          — wi-first nation
      845 (Specialty catch-all)     — wi-first responder, wi-fraternal, wi-military,
                                       wi-outdoors, wi-schools, wi-specialty, wi-sports

    Notable filename quirks:
      wi.medical-college-of-wisconsin.png  — dot not dash in stem
      wi-uw-parkskide.png                  — typo; name corrected to Parkside
      wi-uw-stephens-point.png             — typo; name corrected to Stevens Point
      wi-red-cliff-band-of-lake-sup-erior-chippewa.png — hyphen in Superior; corrected
    """
    NAME_OVERRIDE = {
        # ── wi-standard-issue → 841 ───────────────────────────────────────────
        'wi-amateur-radio':                ('WI - Amateur Radio',                        CAT['Radio / Amateur Radio'],        95, 'Passenger',  WI_STD_SERIES),
        'wi-disabled-motorcycle':          ('WI - Disabled - Motorcycle',                CAT['Disabled / Accessibility'],     95, 'Motorcycle', WI_STD_SERIES),
        'wi-moped':                        ('WI - Moped',                                CAT['Standard Issue'],               88, 'Motorcycle', WI_STD_SERIES),
        'wi-motorcycle-regular':           ('WI - Motorcycle',                           CAT['Standard Issue'],               95, 'Motorcycle', WI_STD_SERIES),
        'wi-standard-issue-2017':          ('WI - Standard Issue - 2017',                CAT['Standard Issue'],               95, 'Passenger',  WI_STD_SERIES),
        'wi-standard-issue-disabled':      ('WI - Standard Issue - Disabled',            CAT['Disabled / Accessibility'],     95, 'Passenger',  WI_STD_SERIES),
        'wi-standard-issue-personalized':  ('WI - Standard Issue - Personalized',        CAT['Standard Issue'],               88, 'Passenger',  WI_STD_SERIES),
        # ── wi-standard-issue → 842 ───────────────────────────────────────────
        'wi-blackout':                     ('WI - Blackout',                             CAT['Standard Issue'],               90, 'Passenger',  WI_ALT_SERIES),
        'wi-retro-yellow':                 ('WI - Retro Yellow',                         CAT['Standard Issue'],               90, 'Passenger',  WI_ALT_SERIES),
        # ── wi-first nation → 844 ─────────────────────────────────────────────
        'wi-bad-river-band-of-lake-superior-chippewa-indians-v1':          ('WI - Bad River Band of Lake Superior Chippewa Indians - V1',         CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-bad-river-band-of-lake-superior-chippewa-indians-v2':          ('WI - Bad River Band of Lake Superior Chippewa Indians - V2',         CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-bad-river-band-of-lake-superior-chippewa-indians-v3':          ('WI - Bad River Band of Lake Superior Chippewa Indians - V3',         CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-ho-chunk-nation-tribal-owned':                                  ('WI - Ho-Chunk Nation - Tribal Owned',                               CAT['Government / Exempt'],        88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-ho-chunk-nation':                                               ('WI - Ho-Chunk Nation',                                              CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-lac-courte-oreilles-chippewa-band-of-lake-superior-indians-o': ('WI - Lac Courte Oreilles Chippewa Band of Lake Superior Indians - O', CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-lac-courte-oreilles-chippewa-band-pride':                      ('WI - Lac Courte Oreilles Chippewa Band - Pride',                    CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-lac-courte-oreilles-chippewa-band-veteran':                    ('WI - Lac Courte Oreilles Chippewa Band - Veteran',                  CAT['Military / Veteran'],         88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-lac-du-flambeau-band-ojibwe':                                  ('WI - Lac du Flambeau Band - Ojibwe',                                CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-menominee-indian-tribe-of-wisconsin-shield':                   ('WI - Menominee Indian Tribe of Wisconsin - Shield',                 CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-menominee-indian-tribe-of-wisconsin-thunderbird':              ('WI - Menominee Indian Tribe of Wisconsin - Thunderbird',            CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-menominee-indian-tribe-of-wisconsin-v1':                       ('WI - Menominee Indian Tribe of Wisconsin - V1',                     CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-menominee-indian-tribe-of-wisconsin-v2':                       ('WI - Menominee Indian Tribe of Wisconsin - V2',                     CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin-bear':                        ('WI - Oneida Indian Tribe of Wisconsin - Bear',                      CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin-clan':                        ('WI - Oneida Indian Tribe of Wisconsin - Clan',                      CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin-eagle':                       ('WI - Oneida Indian Tribe of Wisconsin - Eagle',                     CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin-turtle':                      ('WI - Oneida Indian Tribe of Wisconsin - Turtle',                    CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin-vietnam-vet':                 ('WI - Oneida Indian Tribe of Wisconsin - Vietnam Vet',               CAT['Military / Veteran'],         88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin-wolf':                        ('WI - Oneida Indian Tribe of Wisconsin - Wolf',                      CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-oneida-indian-tribe-of-wisconsin':                             ('WI - Oneida Indian Tribe of Wisconsin',                             CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-red-cliff-band-of-lake-sup-erior-chippewa':                    ('WI - Red Cliff Band of Lake Superior Chippewa',                     CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        'wi-st-croix-chippewa':                                            ('WI - St. Croix Chippewa',                                           CAT['Historical / Commemorative'], 88, 'Passenger', WI_TRIBAL_SERIES),
        # ── wi-first responder → 845 ──────────────────────────────────────────
        'wi-civil-air-patrol':                  ('WI - Civil Air Patrol',                           CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        'wi-emergency-medical-services-red-white': ('WI - Emergency Medical Services - Red White',  CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        'wi-emergency-medical-services-white':  ('WI - Emergency Medical Services - White',         CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        'wi-firefighter-red':                   ('WI - Firefighter - Red',                          CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        'wi-firefighter-white':                 ('WI - Firefighter - White',                        CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        'wi-rescue-squad-member':               ('WI - Rescue Squad Member',                        CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        'wi-state-patrol-motorcycle':           ('WI - State Patrol - Motorcycle',                  CAT['First Responder'],          90, 'Motorcycle', WI_SPECIALTY),
        'wi-wisconsin-state-patrol':            ('WI - Wisconsin State Patrol',                     CAT['First Responder'],          90, 'Passenger',  WI_SPECIALTY),
        # ── wi-fraternal → 845 ────────────────────────────────────────────────
        'wi-freemason':                         ('WI - Freemason',                                  CAT['Fraternal / Civic'],        90, 'Passenger',  WI_SPECIALTY),
        'wi-lions-foundation':                  ('WI - Lions Foundation',                           CAT['Fraternal / Civic'],        90, 'Passenger',  WI_SPECIALTY),
        # ── wi-military → 845 ────────────────────────────────────────────────
        'wi-afghanistan-war-veteran':           ('WI - Afghanistan War Veteran',                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-air-force-cross-medal':             ('WI - Air Force Cross Medal',                      CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-air-force-distinguished-service-medal': ('WI - Air Force Distinguished Service Medal',  CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-airmans-medal':                     ('WI - Airman\'s Medal',                            CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-bronze-star-medal':                 ('WI - Bronze Star Medal',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-coast-guard-distinguished-service-medal': ('WI - Coast Guard Distinguished Service Medal', CAT['Military / Veteran'],    90, 'Passenger',  WI_SPECIALTY),
        'wi-coast-guard-medal':                 ('WI - Coast Guard Medal',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-disabled-veteran':                  ('WI - Disabled Veteran',                           CAT['Disabled / Accessibility'], 90, 'Passenger',  WI_SPECIALTY),
        'wi-distinguished-flying-cross-medal':  ('WI - Distinguished Flying Cross Medal',           CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-distinguished-service-cross-medal': ('WI - Distinguished Service Cross Medal',          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-distinguished-service-medal':       ('WI - Distinguished Service Medal',                CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-ex-prisoner-of-war':                ('WI - Ex-Prisoner of War',                         CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-gold-star-family':                  ('WI - Gold Star Family',                           CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-iraq-war-veteran':                  ('WI - Iraq War Veteran',                           CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-korean-war-veteran':                ('WI - Korean War Veteran',                         CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-lao-veterans-of-america':           ('WI - Lao Veterans of America',                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-legion-of-merit-medal':             ('WI - Legion of Merit Medal',                      CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-medal-of-honor':                    ('WI - Medal of Honor',                             CAT['Military / Veteran'],       95, 'Passenger',  WI_SPECIALTY),
        'wi-military-white':                    ('WI - Military - White',                           CAT['Military / Veteran'],       88, 'Passenger',  WI_SPECIALTY),
        'wi-navy-and-marine-corps-medal':       ('WI - Navy and Marine Corps Medal',                CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-navy-cross-medal':                  ('WI - Navy Cross Medal',                           CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-navy-distinguished-service-medal':  ('WI - Navy Distinguished Service Medal',           CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-noble-eagle':                       ('WI - Noble Eagle',                                CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-pearl-harbor-survivor':             ('WI - Pearl Harbor Survivor',                      CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-persian-gulf-war-veteran':          ('WI - Persian Gulf War Veteran',                   CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-purple-heart-combat-wounded-veteran': ('WI - Purple Heart - Combat Wounded Veteran',    CAT['Military / Veteran'],       95, 'Passenger',  WI_SPECIALTY),
        'wi-silver-star-medal':                 ('WI - Silver Star Medal',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-soldiers-medal':                    ('WI - Soldiers Medal',                             CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-somalia-war-veteran':               ('WI - Somalia War Veteran',                        CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-air-force-academy':              ('WI - US Air Force Academy',                       CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-air-force-reserve':              ('WI - US Air Force Reserve',                       CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-air-force-retired':              ('WI - US Air Force - Retired',                     CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-air-force-veteran':              ('WI - US Air Force - Veteran',                     CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-air-force-woman-veteran':        ('WI - US Air Force - Woman Veteran',               CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-air-force':                      ('WI - US Air Force',                               CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-army-reserve':                   ('WI - US Army Reserve',                            CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-army-retired':                   ('WI - US Army - Retired',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-army-veteran':                   ('WI - US Army - Veteran',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-army-woman-veteran':             ('WI - US Army - Woman Veteran',                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-army':                           ('WI - US Army',                                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-coast-guard-academy':            ('WI - US Coast Guard Academy',                     CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-coast-guard-reserve':            ('WI - US Coast Guard Reserve',                     CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-coast-guard-retired':            ('WI - US Coast Guard - Retired',                   CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-coast-guard-veteran':            ('WI - US Coast Guard - Veteran',                   CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-coast-guard-woman-veteran':      ('WI - US Coast Guard - Woman Veteran',             CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-coast-guard':                    ('WI - US Coast Guard',                             CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-marine-corps-reserve':           ('WI - US Marine Corps Reserve',                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-marine-corps-retired':           ('WI - US Marine Corps - Retired',                  CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-marine-corps-veteran':           ('WI - US Marine Corps - Veteran',                  CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-marine-corps-woman-veteran':     ('WI - US Marine Corps - Woman Veteran',            CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-marine-corps':                   ('WI - US Marine Corps',                            CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-merchant-marine-academy':        ('WI - US Merchant Marine Academy',                 CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-military-academy':               ('WI - US Military Academy',                        CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-naval-academy':                  ('WI - US Naval Academy',                           CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-navy-reserve':                   ('WI - US Navy Reserve',                            CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-navy-retired':                   ('WI - US Navy - Retired',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-navy-veteran':                   ('WI - US Navy - Veteran',                          CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-navy-woman-veteran':             ('WI - US Navy - Woman Veteran',                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-navy':                           ('WI - US Navy',                                    CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-us-veteran-motorcycle-v1':          ('WI - US Veteran - Motorcycle - V1',               CAT['Military / Veteran'],       90, 'Motorcycle', WI_SPECIALTY),
        'wi-us-veteran-motorcycle-v2':          ('WI - US Veteran - Motorcycle - V2',               CAT['Military / Veteran'],       90, 'Motorcycle', WI_SPECIALTY),
        'wi-vietnam-war-veteran':               ('WI - Vietnam War Veteran',                        CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-wisconsin-national-guard':          ('WI - Wisconsin National Guard',                   CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-wisconsin-salutes-veterans':        ('WI - Wisconsin Salutes Veterans',                 CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        'wi-world-war-ii-veteran':              ('WI - World War II Veteran',                       CAT['Military / Veteran'],       90, 'Passenger',  WI_SPECIALTY),
        # ── wi-non-passenger-government → 843 ────────────────────────────────
        'wi-apportioned-full-trailer':                  ('WI - Apportioned Full Trailer',                   CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-apportioned-power-unit-black':              ('WI - Apportioned Power Unit - Black',             CAT['Government / Exempt'],          88, 'Commercial', WI_NONPASS_SERIES),
        'wi-apportioned-power-unit-red':                ('WI - Apportioned Power Unit - Red',               CAT['Government / Exempt'],          88, 'Commercial', WI_NONPASS_SERIES),
        'wi-apportioned-semi-trailer':                  ('WI - Apportioned Semi-Trailer',                   CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-autocycle':                                 ('WI - Autocycle',                                  CAT['Government / Exempt'],          88, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-bus':                                       ('WI - Bus',                                        CAT['Government / Exempt'],          88, 'Commercial', WI_NONPASS_SERIES),
        'wi-dealer-motorcycle':                         ('WI - Dealer - Motorcycle',                        CAT['Dealer / Manufacturer'],        90, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-demonstrator-tractor':                      ('WI - Demonstrator - Tractor',                     CAT['Dealer / Manufacturer'],        88, 'Commercial', WI_NONPASS_SERIES),
        'wi-demonstrator-trailer-semi-trailer':         ('WI - Demonstrator - Trailer Semi-Trailer',        CAT['Dealer / Manufacturer'],        88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-demonstrator-truck':                        ('WI - Demonstrator - Truck',                       CAT['Dealer / Manufacturer'],        88, 'Commercial', WI_NONPASS_SERIES),
        'wi-distributor-motorcycle':                    ('WI - Distributor - Motorcycle',                   CAT['Dealer / Manufacturer'],        88, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-distributor':                               ('WI - Distributor',                                CAT['Dealer / Manufacturer'],        88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-drivers-education':                         ('WI - Drivers Education',                          CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-farm-trailer':                              ('WI - Farm Trailer',                               CAT['Agricultural'],                 90, 'Trailer',    WI_NONPASS_SERIES),
        'wi-farm-truck':                                ('WI - Farm Truck',                                 CAT['Agricultural'],                 90, 'Commercial', WI_NONPASS_SERIES),
        'wi-finance-company':                           ('WI - Finance Company',                            CAT['Dealer / Manufacturer'],        88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-fleet':                                     ('WI - Fleet',                                      CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-heavy-farm-truck':                          ('WI - Heavy Farm Truck',                           CAT['Agricultural'],                 90, 'Commercial', WI_NONPASS_SERIES),
        'wi-heavy-trailer':                             ('WI - Heavy Trailer',                              CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-heavy-truck':                               ('WI - Heavy Truck',                                CAT['Government / Exempt'],          88, 'Commercial', WI_NONPASS_SERIES),
        'wi-historic-military-vehicle':                 ('WI - Historic Military Vehicle',                  CAT['Historical / Commemorative'],   88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-hobbyist-motorcycle':                       ('WI - Hobbyist - Motorcycle',                      CAT['Other / Specialty'],            88, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-hobbyist':                                  ('WI - Hobbyist',                                   CAT['Other / Specialty'],            88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-human-service-vehicle':                     ('WI - Human Service Vehicle',                      CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-light-truck':                               ('WI - Light Truck',                                CAT['Government / Exempt'],          88, 'Commercial', WI_NONPASS_SERIES),
        'wi-low-speed-vehicle':                         ('WI - Low Speed Vehicle',                          CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-manufacturer-motorcycle':                   ('WI - Manufacturer - Motorcycle',                  CAT['Dealer / Manufacturer'],        88, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-manufacturer':                              ('WI - Manufacturer',                               CAT['Dealer / Manufacturer'],        88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-motor-vehicle-dealer':                      ('WI - Motor Vehicle Dealer',                       CAT['Dealer / Manufacturer'],        90, 'Passenger',  WI_NONPASS_SERIES),
        'wi-motorcycle-moped-dealer':                   ('WI - Motorcycle Moped Dealer',                    CAT['Dealer / Manufacturer'],        90, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-motorhome-v1':                              ('WI - Motorhome - V1',                             CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-motorhome-v2':                              ('WI - Motorhome - V2',                             CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-municipal-motorcycle':                      ('WI - Municipal - Motorcycle',                     CAT['Government / Exempt'],          88, 'Motorcycle', WI_NONPASS_SERIES),
        'wi-municipal':                                 ('WI - Municipal',                                  CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-official':                                  ('WI - Official',                                   CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-recreational-vehicle-dealer':               ('WI - Recreational Vehicle Dealer',                CAT['Dealer / Manufacturer'],        88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-rv-trailer-v1':                             ('WI - RV Trailer - V1',                            CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-rv-trailer-v2':                             ('WI - RV Trailer - V2',                            CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-semi-trailer':                              ('WI - Semi-Trailer',                               CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-special-designed-vehicle-v1':               ('WI - Special Designed Vehicle - V1',              CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-special-designed-vehicle-v2':               ('WI - Special Designed Vehicle - V2',              CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-special-x':                                 ('WI - Special X',                                  CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-state-owned':                               ('WI - State Owned',                                CAT['Government / Exempt'],          88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-tractor':                                   ('WI - Tractor',                                    CAT['Agricultural'],                 88, 'Commercial', WI_NONPASS_SERIES),
        'wi-trailer-dealer':                            ('WI - Trailer Dealer',                             CAT['Dealer / Manufacturer'],        88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-transferable-trailer':                      ('WI - Transferable Trailer',                       CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        'wi-transporter':                               ('WI - Transporter',                                CAT['Government / Exempt'],          88, 'Commercial', WI_NONPASS_SERIES),
        'wi-wholesaler':                                ('WI - Wholesaler',                                 CAT['Dealer / Manufacturer'],        88, 'Passenger',  WI_NONPASS_SERIES),
        'wi-za-trailer':                                ('WI - ZA Trailer',                                 CAT['Government / Exempt'],          88, 'Trailer',    WI_NONPASS_SERIES),
        # ── wi-outdoors → 845 ────────────────────────────────────────────────
        'wi-county-forests':                    ('WI - County Forests',                             CAT['Conservation / Environment'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-cranes':                            ('WI - Cranes',                                     CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        'wi-ducks-unlimited':                   ('WI - Ducks Unlimited',                            CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        'wi-endangered-resources-badger':       ('WI - Endangered Resources - Badger',              CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        'wi-endangered-resources-eagle':        ('WI - Endangered Resources - Eagle',               CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        'wi-endangered-resources-wolf':         ('WI - Endangered Resources - Wolf',                CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        'wi-ice-age-trail':                     ('WI - Ice Age Trail',                              CAT['Conservation / Environment'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-musky-clubs-alliance':              ('WI - Musky Clubs Alliance',                       CAT['Conservation / Environment'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-rocky-mountain-elk-foundation':     ('WI - Rocky Mountain Elk Foundation',              CAT['Conservation / Environment'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-trout-unlimited':                   ('WI - Trout Unlimited',                            CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        'wi-whitetails-unlimited':              ('WI - Whitetails Unlimited',                       CAT['Conservation / Environment'],   90, 'Passenger',  WI_SPECIALTY),
        # ── wi-schools → 845 ─────────────────────────────────────────────────
        'wi-marquette-university':              ('WI - Marquette University',                       CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-eau-claire':                     ('WI - UW Eau Claire',                              CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-green-bay':                      ('WI - UW Green Bay',                               CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-la-crosse':                      ('WI - UW La Crosse',                               CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-madison':                        ('WI - UW Madison',                                 CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-milwaukee':                      ('WI - UW Milwaukee',                               CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-oshkosh':                        ('WI - UW Oshkosh',                                 CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-parkskide':                      ('WI - UW Parkside',                                CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-platteville':                    ('WI - UW Platteville',                             CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-river-falls':                    ('WI - UW River Falls',                             CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-stephens-point':                 ('WI - UW Stevens Point',                           CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-stout':                          ('WI - UW Stout',                                   CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-superior':                       ('WI - UW Superior',                                CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi-uw-whitewater':                     ('WI - UW Whitewater',                              CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        'wi.medical-college-of-wisconsin':      ('WI - Medical College of Wisconsin',               CAT['School'],                       90, 'Passenger',  WI_SPECIALTY),
        # ── wi-specialty → 845 ───────────────────────────────────────────────
        'wi-antique-motorcycle':                ('WI - Antique - Motorcycle',                       CAT['Historical / Commemorative'],   88, 'Motorcycle', WI_SPECIALTY),
        'wi-antique':                           ('WI - Antique',                                    CAT['Historical / Commemorative'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-celebrate-children-foundation-1999-2010': ('WI - Celebrate Children Foundation - 1999-2010', CAT['Health & Awareness'],      88, 'Passenger',  WI_SPECIALTY),
        'wi-celebrate-children-foundation-2010-2016': ('WI - Celebrate Children Foundation - 2010-2016', CAT['Health & Awareness'],      88, 'Passenger',  WI_SPECIALTY),
        'wi-celebrate-children-foundation-current':   ('WI - Celebrate Children Foundation - Current',   CAT['Health & Awareness'],      88, 'Passenger',  WI_SPECIALTY),
        'wi-choose-life-wisconsin-inc':         ('WI - Choose Life Wisconsin Inc',                  CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-collector-motorcycle':              ('WI - Collector - Motorcycle',                     CAT['Historical / Commemorative'],   88, 'Motorcycle', WI_SPECIALTY),
        'wi-collector-special':                 ('WI - Collector - Special',                        CAT['Historical / Commemorative'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-collector':                         ('WI - Collector',                                  CAT['Historical / Commemorative'],   88, 'Passenger',  WI_SPECIALTY),
        'wi-cure-childhood-cancer':             ('WI - Cure Childhood Cancer',                      CAT['Health & Awareness'],           88, 'Passenger',  WI_SPECIALTY),
        'wi-donate-life-wisconsin':             ('WI - Donate Life Wisconsin',                      CAT['Health & Awareness'],           88, 'Passenger',  WI_SPECIALTY),
        'wi-harley-davidson-share-the-road':    ('WI - Harley-Davidson - Share the Road',           CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-in-god-we-trust':                   ('WI - In God We Trust',                            CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-keeping-the-lights-on':             ('WI - Keeping the Lights On',                      CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-law-enforcement-memorial':          ('WI - Law Enforcement Memorial',                   CAT['First Responder'],              88, 'Passenger',  WI_SPECIALTY),
        'wi-nurses-change-lives':               ('WI - Nurses Change Lives',                        CAT['Health & Awareness'],           88, 'Passenger',  WI_SPECIALTY),
        'wi-operating-engineers-local-139':     ('WI - Operating Engineers Local 139',              CAT['Fraternal / Civic'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-road-america-v1':                   ('WI - Road America - V1',                          CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-road-america-v2':                   ('WI - Road America - V2',                          CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-scouting-alumni-eagle-scout':       ('WI - Scouting Alumni - Eagle Scout',              CAT['Fraternal / Civic'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-scouting-alumni':                   ('WI - Scouting Alumni',                            CAT['Fraternal / Civic'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-spay-neuter-adopt':                 ('WI - Spay Neuter Adopt',                          CAT['Other / Specialty'],            88, 'Passenger',  WI_SPECIALTY),
        'wi-suicide-prevention':                ('WI - Suicide Prevention',                         CAT['Health & Awareness'],           88, 'Passenger',  WI_SPECIALTY),
        'wi-versiti':                           ('WI - Versiti',                                    CAT['Health & Awareness'],           88, 'Passenger',  WI_SPECIALTY),
        'wi-wisconsin-womens-health-foundation':('WI - Wisconsin Womens Health Foundation',         CAT['Health & Awareness'],           88, 'Passenger',  WI_SPECIALTY),
        # ── wi-sports → 845 ──────────────────────────────────────────────────
        'wi-golf-wisconsin-v1':                 ('WI - Golf Wisconsin - V1',                        CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
        'wi-golf-wisconsin-v2':                 ('WI - Golf Wisconsin - V2',                        CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
        'wi-golf-wisconsin-v3':                 ('WI - Golf Wisconsin - V3',                        CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
        'wi-green-bay-packers':                 ('WI - Green Bay Packers',                          CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
        'wi-milwaukee-brewers-brew-crew':       ('WI - Milwaukee Brewers - Brew Crew',              CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
        'wi-milwaukee-brewers':                 ('WI - Milwaukee Brewers',                          CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
        'wi-milwaukee-bucks':                   ('WI - Milwaukee Bucks',                            CAT['Sports Team'],                  90, 'Passenger',  WI_SPECIALTY),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class, series = NAME_OVERRIDE[stem]

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     50,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_wv(stem: str, subfolder: str, actual_filename: str):
    """Parse a single WV (West Virginia) plate image from multi-subfolder structure.

    Series routing:
      849 (Standard Issue - 1995 Wild, Wonderful) — wv-standard-issue only
      850 (Specialty - catch-all)                 — all other subfolders
    Region: 49 (West Virginia)
    """
    CATCH = WV_SPECIALTY  # 850

    NAME_OVERRIDE = {
        # ── wv-standard-issue → 849 ───────────────────────────────────────
        'wv-150th-anniversary-license-plate': ('WV - 150th Anniversary',               CAT['Historical / Commemorative'], 88, 'Passenger',  WV_STD_SERIES),
        'wv-amateur-radio':                   ('WV - Amateur Radio',                    CAT['Radio / Amateur Radio'],      95, 'Passenger',  WV_STD_SERIES),
        'wv-antique-vehicle':                 ('WV - Antique Vehicle',                  CAT['Historical / Commemorative'], 88, 'Passenger',  WV_STD_SERIES),
        'wv-classic-car':                     ('WV - Classic Car',                      CAT['Historical / Commemorative'], 88, 'Passenger',  WV_STD_SERIES),
        'wv-mobility-impaired':               ('WV - Mobility Impaired',                CAT['Disabled / Accessibility'],   90, 'Passenger',  WV_STD_SERIES),
        'wv-standard-issue-1995':             ('WV - Standard Issue - 1995',            CAT['Standard Issue'],             95, 'Passenger',  WV_STD_SERIES),
        'wv-standard-issue-1995-personalized':('WV - Standard Issue - 1995 - Personalized', CAT['Standard Issue'],         88, 'Passenger',  WV_STD_SERIES),
        # ── wv-first-responders → 850 ─────────────────────────────────────
        'wv-certified-firefighter':           ('WV - Certified Firefighter',            CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-deputy-sheriffs-association':     ('WV - Deputy Sheriffs Association',       CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-emergency-medical-services':      ('WV - Emergency Medical Services',        CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-fire-fighter':                    ('WV - Fire Fighter',                      CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-fraternal-order-of-police':       ('WV - Fraternal Order of Police',         CAT['First Responder'],            90, 'Passenger',  CATCH),
        'wv-professional-firefighter':        ('WV - Professional Firefighter',          CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-volunteer-firefighter':           ('WV - Volunteer Firefighter',             CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-wounded-in-the-line-of-duty':     ('WV - Wounded in the Line of Duty',       CAT['First Responder'],            88, 'Passenger',  CATCH),
        # ── wv-fraternal → 850 ────────────────────────────────────────────
        'wv-american-legion':                         ('WV - American Legion',                          CAT['Fraternal / Civic'],          90, 'Passenger',  CATCH),
        'wv-benevolent-protective-order-of-elks':     ('WV - Benevolent Protective Order of Elks',      CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-beni-kedem-temple':                       ('WV - Beni Kedem Temple',                         CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-f-a-m-p-h-a':                             ('WV - F.A.M.P.H.A.',                              CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-knights-of-columbus':                     ('WV - Knights of Columbus',                       CAT['Fraternal / Civic'],          90, 'Passenger',  CATCH),
        'wv-lions-international':                     ('WV - Lions International',                       CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-mason':                                   ('WV - Mason',                                     CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-osiris-shriner':                          ('WV - Osiris Shriner',                            CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-rotary-international':                    ('WV - Rotary International',                      CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        # ── wv-military → 850 ────────────────────────────────────────────
        'wv-82nd-airborne-division-association': ('WV - 82nd Airborne Division Association', CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-air-force-cross':                    ('WV - Air Force Cross',                    CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-air-force-reserves':                 ('WV - Air Force Reserves',                 CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-air-force-retired':                  ('WV - Air Force Retired',                  CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-air-medal':                          ('WV - Air Medal',                          CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-air-national-guard':                 ('WV - Air National Guard',                 CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-army-national-guard':                ('WV - Army National Guard',                CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-army-reserves':                      ('WV - Army Reserves',                      CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-army-retired':                       ('WV - Army Retired',                       CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-bronze-star':                        ('WV - Bronze Star',                        CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-coast-guard-reserves':               ('WV - Coast Guard Reserves',               CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-coast-guard-retired':                ('WV - Coast Guard Retired',                CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-combat-infantry-badge':              ('WV - Combat Infantry Badge',              CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-combat-medic':                       ('WV - Combat Medic',                       CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-disabled-american-veterans':         ('WV - Disabled American Veterans',         CAT['Military / Veteran'],        90, 'Passenger',  CATCH),
        'wv-disabled-veterans':                  ('WV - Disabled Veterans',                  CAT['Military / Veteran'],        90, 'Passenger',  CATCH),
        'wv-disabled-veterans-mobility-impaired':('WV - Disabled Veterans - Mobility Impaired', CAT['Military / Veteran'],     88, 'Passenger',  CATCH),
        'wv-distinguished-flying-cross':         ('WV - Distinguished Flying Cross',         CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-distinguished-service-cross':        ('WV - Distinguished Service Cross',        CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-former-prisoner-of-war':             ('WV - Former Prisoner of War',             CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-gold-star-family':                   ('WV - Gold Star Family',                   CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-korean-war-veteran':                 ('WV - Korean War Veteran',                 CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-marine-corps-league':                ('WV - Marine Corps League',                CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-marine-corps-reserves':              ('WV - Marine Corps Reserves',              CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-marines-corps-retired':              ('WV - Marines Corps Retired',              CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-medal-of-honor':                     ('WV - Medal of Honor',                     CAT['Military / Veteran'],        90, 'Passenger',  CATCH),
        'wv-navy-cross':                         ('WV - Navy Cross',                         CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-navy-reserves':                      ('WV - Navy Reserves',                      CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-navy-retired':                       ('WV - Navy Retired',                       CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-pearl-harbor-survivor':              ('WV - Pearl Harbor Survivor',              CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-persian-gulf-veteran':               ('WV - Persian Gulf Veteran',               CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-purple-heart':                       ('WV - Purple Heart',                       CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-silver-star':                        ('WV - Silver Star',                        CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-veteran':                            ('WV - Veteran',                            CAT['Military / Veteran'],        95, 'Passenger',  CATCH),
        'wv-vietnam-war-veteran':                ('WV - Vietnam War Veteran',                CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-war-on-terrorism-afghanistan':       ('WV - War on Terrorism - Afghanistan',     CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-war-on-terrorism-iraq':              ('WV - War on Terrorism - Iraq',            CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-women-veterans':                     ('WV - Women Veterans',                     CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        'wv-world-war-ii-veteran':               ('WV - World War II Veteran',               CAT['Military / Veteran'],        88, 'Passenger',  CATCH),
        # ── wv-outdoors → 850 ────────────────────────────────────────────
        'wv-protect-pollinators':      ('WV - Protect Pollinators',       CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-whitewater-rafting':       ('WV - Whitewater Rafting',         CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-wildlife-bluebird':        ('WV - Wildlife - Bluebird',        CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-wildlife-box-turtle':      ('WV - Wildlife - Box Turtle',      CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-wildlife-brook-trout':     ('WV - Wildlife - Brook Trout',     CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-wildlife-deer':            ('WV - Wildlife - Deer',            CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-wildlife-deer (2)':        ('WV - Wildlife - Deer - V2',       CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        'wv-wildlife-eastern-elk':     ('WV - Wildlife - Eastern Elk',     CAT['Conservation / Environment'],  88, 'Passenger',  CATCH),
        # ── wv-schools → 850 ─────────────────────────────────────────────
        'wv-alderson-broaddus-college':  ('WV - Alderson Broaddus College',   CAT['School'],  88, 'Passenger',  CATCH),
        'wv-concord-college':            ('WV - Concord College',              CAT['School'],  88, 'Passenger',  CATCH),
        'wv-davis-and-elkins':           ('WV - Davis and Elkins',             CAT['School'],  88, 'Passenger',  CATCH),
        'wv-marshall-university':        ('WV - Marshall University',          CAT['School'],  90, 'Passenger',  CATCH),
        'wv-penn-state-alumni':          ('WV - Penn State Alumni',            CAT['School'],  88, 'Passenger',  CATCH),
        'wv-virginia-tech':              ('WV - Virginia Tech',                CAT['School'],  88, 'Passenger',  CATCH),
        'wv-wesleyan-college':           ('WV - Wesleyan College',             CAT['School'],  88, 'Passenger',  CATCH),
        'wv-west-virginia-state-college':('WV - West Virginia State College',  CAT['School'],  88, 'Passenger',  CATCH),
        'wv-west-virginia-university':   ('WV - West Virginia University',     CAT['School'],  90, 'Passenger',  CATCH),
        'wv-wv-tech':                    ('WV - WV Tech',                      CAT['School'],  88, 'Passenger',  CATCH),
        # ── wv-specialty → 850 ───────────────────────────────────────────
        'wv-9-11-commemorative':                      ('WV - 9-11 Commemorative',                         CAT['Historical / Commemorative'], 88, 'Passenger',  CATCH),
        'wv-9-11-commemorative-personalized':         ('WV - 9-11 Commemorative - Personalized',          CAT['Historical / Commemorative'], 88, 'Passenger',  CATCH),
        'wv-back-the-blue':                           ('WV - Back the Blue',                               CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-back-the-blue-v2':                        ('WV - Back the Blue - V2',                          CAT['First Responder'],            88, 'Passenger',  CATCH),
        'wv-breast-cancer-awareness':                 ('WV - Breast Cancer Awareness',                     CAT['Health & Awareness'],         88, 'Passenger',  CATCH),
        'wv-character-education':                     ('WV - Character Education',                         CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-contractors-association-of-wv':           ('WV - Contractors Association of WV',               CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-cure-childhood-cancer':                   ('WV - Cure Childhood Cancer',                       CAT['Health & Awareness'],         88, 'Passenger',  CATCH),
        'wv-educator':                                ('WV - Educator',                                    CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-ffa-4h':                                  ('WV - FFA 4H',                                      CAT['Agricultural'],               88, 'Passenger',  CATCH),
        'wv-friends-of-coal':                         ('WV - Friends of Coal',                             CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-gas-oil-association-of-wv':               ('WV - Gas Oil Association of WV',                   CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-in-god-we-trust':                         ('WV - In God We Trust',                             CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-league-of-postmasters':                   ('WV - League of Postmasters',                       CAT['Fraternal / Civic'],          88, 'Passenger',  CATCH),
        'wv-organ-donor':                             ('WV - Organ Donor',                                 CAT['Health & Awareness'],         88, 'Passenger',  CATCH),
        'wv-pupil-transportation':                    ('WV - Pupil Transportation',                        CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-telecommunicator':                        ('WV - Telecommunicator',                            CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-united-we-stand':                         ('WV - United We Stand',                             CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-united-we-stand-personalized':            ('WV - United We Stand - Personalized',              CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-wv-chiropractic-society':                 ('WV - WV Chiropractic Society',                     CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        'wv-wv-square-and-round-dance-federation':    ('WV - WV Square and Round Dance Federation',        CAT['Other / Specialty'],          88, 'Passenger',  CATCH),
        # ── wv-sports → 850 ──────────────────────────────────────────────
        'wv-bowlers':              ('WV - Bowlers',                    CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-carl-edwards':  ('WV - NASCAR - Carl Edwards',      CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-dale-earnhardt':('WV - NASCAR - Dale Earnhardt',    CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-dale-earnhardt-jr':('WV - NASCAR - Dale Earnhardt Jr.', CAT['Sports Team'], 88, 'Passenger', CATCH),
        'wv-nascar-jeff-gordon-v1':('WV - NASCAR - Jeff Gordon - V1',  CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-jeff-gordon-v2':('WV - NASCAR - Jeff Gordon - V2',  CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-jimmie-johnson':('WV - NASCAR - Jimmie Johnson',    CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-kevin-harvick': ('WV - NASCAR - Kevin Harvick',     CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-matt-kenseth':  ('WV - NASCAR - Matt Kenseth',      CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-standard':      ('WV - NASCAR - Standard',          CAT['Sports Team'],  88, 'Passenger',  CATCH),
        'wv-nascar-tony-stewart':  ('WV - NASCAR - Tony Stewart',      CAT['Sports Team'],  88, 'Passenger',  CATCH),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class, series = NAME_OVERRIDE[stem]

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     49,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_wy(stem: str, subfolder: str, actual_filename: str):
    """Parse a single WY (Wyoming) plate image from multi-subfolder structure.

    Series routing based on filename prefix:
      851 (Standard Issue - 2025 - Prestige)    — wy-2025-* and wy-2026-* and wy-pioneer
      852 (Standard Issue - 2016 - Green River) — wy-2016-*
    Region: 51 (Wyoming)
    """
    # Determine era from filename prefix
    if stem.startswith('wy-2025-') or stem.startswith('wy-2026-') or stem == 'wy-pioneer':
        era = WY_2025_SERIES
        era_label = '2025'
    elif stem.startswith('wy-2016-'):
        era = WY_2016_SERIES
        era_label = '2016'
    else:
        return None

    NAME_OVERRIDE = {
        # ── wy-standard-issue ───────────────────────────────────────────
        'wy-2016-radio-amateur':                   ('WY - Amateur Radio - 2016',                    CAT['Radio / Amateur Radio'],       95, 'Passenger',  WY_2016_SERIES),
        'wy-2016-radio-amateur-truck':             ('WY - Amateur Radio - Truck - 2016',            CAT['Radio / Amateur Radio'],       90, 'Commercial', WY_2016_SERIES),
        'wy-2016-standard-issue-2016-green river': ('WY - Standard Issue - 2016 - Green River',    CAT['Standard Issue'],              95, 'Passenger',  WY_2016_SERIES),
        'wy-2016-street-rod-and-custom-vehicle':   ('WY - Street Rod and Custom Vehicle - 2016',   CAT['Other / Specialty'],           88, 'Passenger',  WY_2016_SERIES),
        'wy-2025-amateur-radio':                   ('WY - Amateur Radio - 2025',                    CAT['Radio / Amateur Radio'],       95, 'Passenger',  WY_2025_SERIES),
        'wy-2025-amateur-radio-truck':             ('WY - Amateur Radio - Truck - 2025',            CAT['Radio / Amateur Radio'],       90, 'Commercial', WY_2025_SERIES),
        'wy-2025-standard-issue-2025-prestige':    ('WY - Standard Issue - 2025 - Prestige',        CAT['Standard Issue'],              95, 'Passenger',  WY_2025_SERIES),
        'wy-2025-street-rod':                      ('WY - Street Rod - 2025',                       CAT['Other / Specialty'],           88, 'Passenger',  WY_2025_SERIES),
        # ── wy-first-responder ─────────────────────────────────────────
        'wy-2016-emt':                             ('WY - EMT - 2016',                              CAT['First Responder'],             88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-firefighter':                     ('WY - Firefighter - 2016',                      CAT['First Responder'],             88, 'Passenger',  WY_2016_SERIES),
        'wy-2025-emt':                             ('WY - EMT - 2025',                              CAT['First Responder'],             88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-firefighter':                     ('WY - Firefighter - 2025',                      CAT['First Responder'],             88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-search-and-rescue':               ('WY - Search and Rescue - 2025',                CAT['First Responder'],             88, 'Passenger',  WY_2025_SERIES),
        # ── wy-military ──────────────────────────────────────────────
        'wy-2016-disabled-veteran':                ('WY - Disabled Veteran - 2016',                 CAT['Military / Veteran'],          90, 'Passenger',  WY_2016_SERIES),
        'wy-2016-former-prisoner-of-war':          ('WY - Former Prisoner of War - 2016',           CAT['Military / Veteran'],          88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-gold-star-plates':                ('WY - Gold Star - 2016',                        CAT['Military / Veteran'],          88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-national-guard':                  ('WY - National Guard - 2016',                   CAT['Military / Veteran'],          88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-pearl-harbor-survivor':           ('WY - Pearl Harbor Survivor - 2016',            CAT['Military / Veteran'],          88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-purple-heart':                    ('WY - Purple Heart - 2016',                     CAT['Military / Veteran'],          88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-veteran-air-force':               ('WY - Veteran - Air Force - 2016',              CAT['Military / Veteran'],          90, 'Passenger',  WY_2016_SERIES),
        'wy-2016-veteran-army':                    ('WY - Veteran - Army - 2016',                   CAT['Military / Veteran'],          90, 'Passenger',  WY_2016_SERIES),
        'wy-2016-veteran-coast-guard':             ('WY - Veteran - Coast Guard - 2016',            CAT['Military / Veteran'],          90, 'Passenger',  WY_2016_SERIES),
        'wy-2016-veteran-merchant-marines':        ('WY - Veteran - Merchant Marines - 2016',       CAT['Military / Veteran'],          88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-veteran-navy':                    ('WY - Veteran - Navy - 2016',                   CAT['Military / Veteran'],          90, 'Passenger',  WY_2016_SERIES),
        'wy-2016-veteran-usmc':                    ('WY - Veteran - USMC - 2016',                   CAT['Military / Veteran'],          90, 'Passenger',  WY_2016_SERIES),
        'wy-2025-air-force':                       ('WY - Air Force - 2025',                        CAT['Military / Veteran'],          90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-army':                            ('WY - Army - 2025',                             CAT['Military / Veteran'],          90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-coast-guard':                     ('WY - Coast Guard - 2025',                      CAT['Military / Veteran'],          90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-combat-wounded-purple-heart':     ('WY - Combat Wounded - Purple Heart - 2025',    CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-disabled-veteran':                ('WY - Disabled Veteran - 2025',                 CAT['Military / Veteran'],          90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-gold-star-family':                ('WY - Gold Star Family - 2025',                 CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-marine-corps':                    ('WY - Marine Corps - 2025',                     CAT['Military / Veteran'],          90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-merchant-marine':                 ('WY - Merchant Marine - 2025',                  CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-national-guard':                  ('WY - National Guard - 2025',                   CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-navy':                            ('WY - Navy - 2025',                             CAT['Military / Veteran'],          90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-pearl-harbor-survivor':           ('WY - Pearl Harbor Survivor - 2025',            CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-prisoner-of-war':                 ('WY - Prisoner of War - 2025',                  CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-space-force':                     ('WY - Space Force - 2025',                      CAT['Military / Veteran'],          88, 'Passenger',  WY_2025_SERIES),
        # ── wy-tribal nation ──────────────────────────────────────────
        'wy-2016-tribal-plates-eastern-shoshone':  ('WY - Tribal - Eastern Shoshone - 2016',        CAT['Other / Specialty'],           88, 'Passenger',  WY_2016_SERIES),
        'wy-2016-tribal-plates-northern-arapahoe': ('WY - Tribal - Northern Arapahoe - 2016',       CAT['Other / Specialty'],           88, 'Passenger',  WY_2016_SERIES),
        'wy-2025-eastern-shoshone-tribe':          ('WY - Tribal - Eastern Shoshone - 2025',        CAT['Other / Specialty'],           88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-northern-arapahoe-tribe':         ('WY - Tribal - Northern Arapahoe - 2025',       CAT['Other / Specialty'],           88, 'Passenger',  WY_2025_SERIES),
        # ── wy-specialty ─────────────────────────────────────────────
        'wy-2016-university-of-wyoming':           ('WY - University of Wyoming - 2016',            CAT['School'],                      90, 'Passenger',  WY_2016_SERIES),
        'wy-2016-wildlife-conservation-plates':    ('WY - Wildlife Conservation - 2016',            CAT['Conservation / Environment'],  88, 'Passenger',  WY_2016_SERIES),
        'wy-2025-donate-life':                     ('WY - Donate Life - 2025',                      CAT['Health & Awareness'],          88, 'Passenger',  WY_2025_SERIES),
        'wy-2025-university-of-wyoming':           ('WY - University of Wyoming - 2025',            CAT['School'],                      90, 'Passenger',  WY_2025_SERIES),
        'wy-2025-wildlife-conservation':           ('WY - Wildlife Conservation - 2025',            CAT['Conservation / Environment'],  88, 'Passenger',  WY_2025_SERIES),
        'wy-2026-rodeo':                           ('WY - Rodeo - 2026',                            CAT['Other / Specialty'],           88, 'Passenger',  WY_2025_SERIES),
        'wy-pioneer':                              ('WY - Pioneer',                                 CAT['Historical / Commemorative'],  88, 'Passenger',  WY_2025_SERIES),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, vehicle_class, series = NAME_OVERRIDE[stem]

    return {
        'filename':      actual_filename,
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': vehicle_class,
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     51,
        'notes':         [],
        'src_subfolder': subfolder,
    }


def parse_tx(stem: str) -> dict:
    """Parse a single TX (Texas) plate image from a flat subfolder.

    Run with --folder pointing at the specific subfolder, e.g.:
        python import_plates_from_images.py tx --folder "P:\\...\\tx-schools"

    The NAME_OVERRIDE dict grows as each subfolder batch is added.
    """
    # Stems that exist in multiple physical subfolders but have already been imported
    # under a prior series — skip them here to prevent duplicate slug errors.
    _ALREADY_IMPORTED = {
        'tx-come-and-take-it-flag',  # imported in tx-alternatives (series 858)
    }
    if stem in _ALREADY_IMPORTED:
        return None
    NAME_OVERRIDE = {
        # ── tx-schools ───────────────────────────────────────────────────────────
        'tx-abilene-christian-university':           ('TX - Abilene Christian University',             CAT['School'], 90, TX_SCHOOLS),
        'tx-allen-eagles-isd':                       ('TX - Allen Eagles ISD',                         CAT['School'], 90, TX_SCHOOLS),
        'tx-angelo-state-university':                ('TX - Angelo State University',                  CAT['School'], 90, TX_SCHOOLS),
        'tx-arizona-state-university':               ('TX - Arizona State University',                 CAT['School'], 90, TX_SCHOOLS),
        'tx-auburn-university':                      ('TX - Auburn University',                        CAT['School'], 90, TX_SCHOOLS),
        'tx-austin-college-v1':                      ('TX - Austin College - v1',                      CAT['School'], 90, TX_SCHOOLS),
        'tx-austin-college-v2':                      ('TX - Austin College - v2',                      CAT['School'], 90, TX_SCHOOLS),
        'tx-baylor-bears':                           ('TX - Baylor Bears',                             CAT['School'], 90, TX_SCHOOLS),
        'tx-baylor-university':                      ('TX - Baylor University',                        CAT['School'], 90, TX_SCHOOLS),
        'tx-bishop-lynch-friars':                    ('TX - Bishop Lynch Friars',                      CAT['School'], 88, TX_SCHOOLS),
        'tx-boise-state-university':                 ('TX - Boise State University',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-brigham-young-university':               ('TX - Brigham Young University',                 CAT['School'], 90, TX_SCHOOLS),
        'tx-carroll-isd':                            ('TX - Carroll ISD',                              CAT['School'], 90, TX_SCHOOLS),
        'tx-central-catholic-high-school':           ('TX - Central Catholic High School',             CAT['School'], 88, TX_SCHOOLS),
        'tx-clemson-university':                     ('TX - Clemson University',                       CAT['School'], 90, TX_SCHOOLS),
        'tx-colorado-school-of-mines':               ('TX - Colorado School of Mines',                 CAT['School'], 90, TX_SCHOOLS),
        'tx-coppell-cowboys-school':                 ('TX - Coppell Cowboys',                          CAT['School'], 88, TX_SCHOOLS),
        'tx-east-texas-a-m-university':              ('TX - East Texas A&M University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-florida-a-m-university':                 ('TX - Florida A&M University',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-florida-state-university':               ('TX - Florida State University',                 CAT['School'], 90, TX_SCHOOLS),
        'tx-georgia-tech-university':                ('TX - Georgia Tech',                             CAT['School'], 90, TX_SCHOOLS),
        'tx-grambling-state-university':             ('TX - Grambling State University',               CAT['School'], 90, TX_SCHOOLS),
        'tx-highland-park-high-school-scots':        ('TX - Highland Park High School Scots',          CAT['School'], 88, TX_SCHOOLS),
        'tx-houston-community-college':              ('TX - Houston Community College',                CAT['School'], 90, TX_SCHOOLS),
        'tx-iowa-state-university':                  ('TX - Iowa State University',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-jackson-state-university':               ('TX - Jackson State University',                 CAT['School'], 90, TX_SCHOOLS),
        'tx-jesuit-high-school-dallas':              ('TX - Jesuit High School - Dallas',              CAT['School'], 88, TX_SCHOOLS),
        'tx-kansas-state-university':                ('TX - Kansas State University',                  CAT['School'], 90, TX_SCHOOLS),
        'tx-keller-high-school':                     ('TX - Keller High School',                       CAT['School'], 88, TX_SCHOOLS),
        'tx-kilgore-college-rangerettes':            ('TX - Kilgore College Rangerettes',              CAT['School'], 88, TX_SCHOOLS),
        'tx-lake-dallas-high-school':                ('TX - Lake Dallas High School',                  CAT['School'], 88, TX_SCHOOLS),
        'tx-liberty-christian-school':               ('TX - Liberty Christian School',                 CAT['School'], 88, TX_SCHOOLS),
        'tx-longview-high-school':                   ('TX - Longview High School',                     CAT['School'], 88, TX_SCHOOLS),
        'tx-louisiana-state-university':             ('TX - Louisiana State University',               CAT['School'], 90, TX_SCHOOLS),
        'tx-louisiana-state-university-purple':      ('TX - Louisiana State University - Purple',      CAT['School'], 90, TX_SCHOOLS),
        'tx-louisiana-tech-university':              ('TX - Louisiana Tech University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-lubbock-christian-university':           ('TX - Lubbock Christian University',             CAT['School'], 90, TX_SCHOOLS),
        'tx-michigan-state-university':              ('TX - Michigan State University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-midland-high-school':                    ('TX - Midland High School',                      CAT['School'], 88, TX_SCHOOLS),
        'tx-midland-lee-high-school':                ('TX - Midland Lee High School',                  CAT['School'], 88, TX_SCHOOLS),
        'tx-mississippi-state-university':           ('TX - Mississippi State University',             CAT['School'], 90, TX_SCHOOLS),
        'tx-odessa-high-school':                     ('TX - Odessa High School',                       CAT['School'], 88, TX_SCHOOLS),
        'tx-oklahoma-state-university':              ('TX - Oklahoma State University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-penn-state-university':                  ('TX - Penn State University',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-periman-high-school':                    ('TX - Permian High School',                      CAT['School'], 88, TX_SCHOOLS),
        'tx-prairie-view-a-m-university':            ('TX - Prairie View A&M University',              CAT['School'], 90, TX_SCHOOLS),
        'tx-prosper-high-school':                    ('TX - Prosper High School',                      CAT['School'], 88, TX_SCHOOLS),
        'tx-purdue-university':                      ('TX - Purdue University',                        CAT['School'], 90, TX_SCHOOLS),
        'tx-rice-university':                        ('TX - Rice University',                          CAT['School'], 90, TX_SCHOOLS),
        'tx-sam-houston-state-university-v1':        ('TX - Sam Houston State University - v1',        CAT['School'], 90, TX_SCHOOLS),
        'tx-sam-houston-state-university-v2':        ('TX - Sam Houston State University - v2',        CAT['School'], 90, TX_SCHOOLS),
        'tx-sam-houston-state-university-v3':        ('TX - Sam Houston State University - v3',        CAT['School'], 90, TX_SCHOOLS),
        'tx-schreiner-university':                   ('TX - Schreiner University',                     CAT['School'], 90, TX_SCHOOLS),
        'tx-southern-methodist-university-v1':       ('TX - Southern Methodist University - v1',       CAT['School'], 90, TX_SCHOOLS),
        'tx-southern-methodist-university-v2':       ('TX - Southern Methodist University - v2',       CAT['School'], 90, TX_SCHOOLS),
        'tx-southern-university':                    ('TX - Southern University',                      CAT['School'], 90, TX_SCHOOLS),
        'tx-southwestern-university':                ('TX - Southwestern University',                  CAT['School'], 90, TX_SCHOOLS),
        'tx-stephen-f-austin-state-university':      ('TX - Stephen F. Austin State University',       CAT['School'], 90, TX_SCHOOLS),
        'tx-st-marys-university':                    ('TX - St. Mary\'s University',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-sul-ross-state-university':              ('TX - Sul Ross State University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-tarleton-state-university':              ('TX - Tarleton State University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-a-m-university-black':             ('TX - Texas A&M University - Black',             CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-a-m-university-commerce':          ('TX - Texas A&M University - Commerce',          CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-a-m-university-corpus-christi':    ('TX - Texas A&M University - Corpus Christi',    CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-a-m-university-maroon':            ('TX - Texas A&M University - Maroon',            CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-a-m-university-mascot':            ('TX - Texas A&M University - Mascot',            CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-a-m-university-texarkana':         ('TX - Texas A&M University - Texarkana',         CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-christian-university':             ('TX - Texas Christian University',               CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-exes':                             ('TX - Texas Exes',                               CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-exes-blackout':                    ('TX - Texas Exes - Blackout',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-southern-university':              ('TX - Texas Southern University',                CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-state-university':                 ('TX - Texas State University',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-tech-university-v1':               ('TX - Texas Tech University - v1',               CAT['School'], 90, TX_SCHOOLS),
        'tx-texas-tech-university-v2':               ('TX - Texas Tech University - v2',               CAT['School'], 90, TX_SCHOOLS),
        'tx-trinity-university':                     ('TX - Trinity University',                       CAT['School'], 90, TX_SCHOOLS),
        'tx-tyler-junior-college':                   ('TX - Tyler Junior College',                     CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-alabama':                  ('TX - University of Alabama',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-arizona':                  ('TX - University of Arizona',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-arkansas':                 ('TX - University of Arkansas',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-colorado':                 ('TX - University of Colorado',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-florida':                  ('TX - University of Florida',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-georgia':                  ('TX - University of Georgia',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-houston-v1':               ('TX - University of Houston - v1',               CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-houston-v2':               ('TX - University of Houston - v2',               CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-illinois':                 ('TX - University of Illinois',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-indiana':                  ('TX - University of Indiana',                    CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-iowa':                     ('TX - University of Iowa',                       CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-kansas':                   ('TX - University of Kansas',                     CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-kentucky':                 ('TX - University of Kentucky',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-louisiana':                ('TX - University of Louisiana',                  CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-mary-hardin-baylor':       ('TX - University of Mary Hardin-Baylor',         CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-michigan':                 ('TX - University of Michigan',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-mississippi':              ('TX - University of Mississippi',                CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-missouri':                 ('TX - University of Missouri',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-nebraska':                 ('TX - University of Nebraska',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-north-texas':              ('TX - University of North Texas',                CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-notre-dame':               ('TX - University of Notre Dame',                 CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-oklahoma':                 ('TX - University of Oklahoma',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-saint-thomas':             ('TX - University of Saint Thomas',               CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-tennessee':                ('TX - University of Tennessee',                  CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-arlington':          ('TX - University of Texas - Arlington',          CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-dallas':             ('TX - University of Texas - Dallas',             CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-el-paso':            ('TX - University of Texas - El Paso',            CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-longhorns-black':    ('TX - University of Texas Longhorns - Black',    CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-longhorns-orange':   ('TX - University of Texas Longhorns - Orange',   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-md-anderson-cancer-center': ('TX - UT MD Anderson Cancer Center',      CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-rio-grande-valley':  ('TX - University of Texas - Rio Grande Valley',  CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-san-antonio-v1':     ('TX - University of Texas - San Antonio - v1',   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-san-antonio-v2':     ('TX - University of Texas - San Antonio - v2',   CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-texas-tower':              ('TX - University of Texas - Tower',              CAT['School'], 90, TX_SCHOOLS),
        'tx-university-of-virginia':                 ('TX - University of Virginia',                   CAT['School'], 90, TX_SCHOOLS),
        'tx-virginia-tech-university':               ('TX - Virginia Tech',                            CAT['School'], 90, TX_SCHOOLS),
        'tx-west-texas-a-m-university':              ('TX - West Texas A&M University',                CAT['School'], 90, TX_SCHOOLS),
        # ── tx-alternatives ─────────────────────────────────────────────────────────
        'tx-alamo':                                  ('TX - Alamo',                                    CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-black-and-gold':                         ('TX - Black and Gold',                           CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-black-and-white':                        ('TX - Black and White',                          CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-black-and-yellow':                       ('TX - Black and Yellow',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-blue-and-gold':                          ('TX - Blue and Gold',                            CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-brushed-metal-grill':                    ('TX - Brushed Metal Grill',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-camo-green':                             ('TX - Camo - Green',                             CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-camo-pink':                              ('TX - Camo - Pink',                              CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-carbon-fiber':                           ('TX - Carbon Fiber',                             CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-carbon-fiber-v2':                        ('TX - Carbon Fiber - v2',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-classic-auto':                           ('TX - Classic Auto',                             CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-classic-black':                          ('TX - Classic Black',                            CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-classic-black-silver':                   ('TX - Classic Black Silver',                     CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-classic-blue-silver':                    ('TX - Classic Blue Silver',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-classic-pink-silver':                    ('TX - Classic Pink Silver',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-come-and-take-it-flag':                  ('TX - Come and Take It Flag',                    CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-custom-vehicle':                         ('TX - Custom Vehicle',                           CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-deep-in-the-heart-flag':                 ('TX - Deep in the Heart Flag',                   CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-1836':                         ('TX - Lone Star 1836',                           CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-badge':                        ('TX - Lone Star Badge',                          CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-badge-black':                  ('TX - Lone Star Badge - Black',                  CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-black':                        ('TX - Lone Star - Black',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-black-silver-state-of-the-arts': ('TX - Lone Star Black Silver - State of the Arts', CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-blue':                         ('TX - Lone Star - Blue',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-carbon-fiber':                 ('TX - Lone Star Carbon Fiber',                   CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-flag':                         ('TX - Lone Star Flag',                           CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-pink':                         ('TX - Lone Star - Pink',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-red':                          ('TX - Lone Star - Red',                          CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-silver':                       ('TX - Lone Star - Silver',                       CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-lone-star-white':                        ('TX - Lone Star - White',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-love-heart-black':                       ('TX - Love Heart - Black',                       CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-new-texas':                              ('TX - New Texas',                                CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-black':                       ('TX - Small Star - Black',                       CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-blue':                        ('TX - Small Star - Blue',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-green':                       ('TX - Small Star - Green',                       CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-maroon':                      ('TX - Small Star - Maroon',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-orange':                      ('TX - Small Star - Orange',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-pink':                        ('TX - Small Star - Pink',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-purple':                      ('TX - Small Star - Purple',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-red':                         ('TX - Small Star - Red',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-small-star-silver':                      ('TX - Small Star - Silver',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-smile-texas-style':                      ('TX - Smile Texas Style',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-street-rod':                             ('TX - Street Rod',                               CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-4-ever':                           ('TX - Texas 4 Ever',                             CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-barbed-wire-black':                ('TX - Texas Barbed Wire - Black',                CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-barbed-wire-white':                ('TX - Texas Barbed Wire - White',                CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-black-1836':                       ('TX - Texas Black 1836',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-black-1845':                       ('TX - Texas Black 1845',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-blue-1836':                        ('TX - Texas Blue 1836',                          CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-is-home':                          ('TX - Texas Is Home',                            CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-its-like-a-whole-other-country':   ('TX - Texas - It\'s Like a Whole Other Country', CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-pink-1836':                        ('TX - Texas Pink 1836',                          CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-pride':                            ('TX - Texas Pride',                              CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-red-1836':                         ('TX - Texas Red 1836',                           CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-silver-1836':                      ('TX - Texas Silver 1836',                        CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-tough':                            ('TX - Texas Tough',                              CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-tough-black':                      ('TX - Texas Tough - Black',                      CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-vintage-black':                    ('TX - Texas Vintage - Black',                    CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-vintage-blue':                     ('TX - Texas Vintage - Blue',                     CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-vintage-pink':                     ('TX - Texas Vintage - Pink',                     CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-vintage-white':                    ('TX - Texas Vintage - White',                    CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-texas-white-1836':                       ('TX - Texas White 1836',                         CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-western-yoke-black':                     ('TX - Western Yoke - Black',                     CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-western-yoke-white':                     ('TX - Western Yoke - White',                     CAT['Other / Specialty'], 88, TX_ALTERNATIVES),
        'tx-yellow-rose-of-texas':                   ('TX - Yellow Rose of Texas',                     CAT['Other / Specialty'], 88, TX_ALTERNATIVES),

        # ── tx-military ───────────────────────────────────────────────────────────────────────────────
        'tx-11th-armored-cavalry-regiment':                                          ('TX - 11th Armored Cavalry Regiment',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-11th-armored-cavalry-regiment-disabled':                                 ('TX - 11th Armored Cavalry Regiment - Disabled',                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-173rd-airborne-brigade':                                                 ('TX - 173rd Airborne Brigade',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-36th-infantry-division':                                                 ('TX - 36th Infantry Division',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-75th-army-ranger-regiment':                                              ('TX - 75th Army Ranger Regiment',                                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-academy-disabled':                                             ('TX - Air Force Academy - Disabled',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-association':                                                  ('TX - Air Force Association',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-commendation-medal':                                           ('TX - Air Force Commendation Medal',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-commendation-medal-w-valor-':                                  ('TX - Air Force Commendation Medal w/ Valor',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-commendation-medal-w-valor-disabled':                          ('TX - Air Force Commendation Medal w/ Valor - Disabled',                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-cross':                                                        ('TX - Air Force Cross',                                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-force-honorably-discharged':                                         ('TX - Air Force - Honorably Discharged',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-airmans-medal':                                                          ('TX - Airman\'s Medal',                                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-airmans-medal-disabled':                                                 ('TX - Airman\'s Medal - Disabled',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-medal':                                                              ('TX - Air Medal',                                                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-medal-disabled':                                                     ('TX - Air Medal - Disabled',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-medal-disabled-w-handicap':                                          ('TX - Air Medal - Disabled w/ Handicap',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-medal-with-valor-disabled':                                          ('TX - Air Medal w/ Valor - Disabled',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-air-medal-w-valor':                                                      ('TX - Air Medal w/ Valor',                                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-antartica-service-medal':                                                ('TX - Antarctica Service Medal',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-armed-forces-expeditionary-medal':                                       ('TX - Armed Forces Expeditionary Medal',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-armed-forces-expeditionary-medal-disabled':                              ('TX - Armed Forces Expeditionary Medal - Disabled',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-armed-forces-reserve':                                                   ('TX - Armed Forces Reserve',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-armed-forces-service-medal':                                             ('TX - Armed Forces Service Medal',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-armed-forces-service-medal-disabled':                                    ('TX - Armed Forces Service Medal - Disabled',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-arm-of-occupation-medal-disabled':                                       ('TX - Army of Occupation Medal - Disabled',                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-commendation-medal':                                                ('TX - Army Commendation Medal',                                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-commendation-medal-with-valor':                                     ('TX - Army Commendation Medal w/ Valor',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-commendation-medal-with-valor-disabled':                            ('TX - Army Commendation Medal w/ Valor - Disabled',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-disabled':                                                          ('TX - Army - Disabled',                                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-honorably-discharged':                                              ('TX - Army - Honorably Discharged',                                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-master-aviator-badge-disabled':                                     ('TX - Army Master Aviator Badge - Disabled',                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-medal-of-honor-disabled':                                           ('TX - Army Medal of Honor - Disabled',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-of-occupation-medal':                                               ('TX - Army of Occupation Medal',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-ranger':                                                            ('TX - Army Ranger',                                                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-ranger-disabled':                                                   ('TX - Army Ranger - Disabled',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-special-forces':                                                    ('TX - Army Special Forces',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-army-special-forces-disabled':                                           ('TX - Army Special Forces - Disabled',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-borinqueneers-congressional-gold-medal':                                 ('TX - Borinqueneers Congressional Gold Medal',                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-borinqueneers-congressional-gold-medal-disabled':                        ('TX - Borinqueneers Congressional Gold Medal - Disabled',                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-bronze-star-medal':                                                      ('TX - Bronze Star Medal',                                                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-bronze-star-medal-disabled':                                             ('TX - Bronze Star Medal - Disabled',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-bronze-star-medal-w-valor':                                              ('TX - Bronze Star Medal w/ Valor',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-bronze-star-medal-w-valor-disabled':                                     ('TX - Bronze Star Medal w/ Valor - Disabled',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-burn-pit':                                                               ('TX - Burn Pit',                                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-china-service-medal':                                                    ('TX - China Service Medal',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-china-service-medal-disabled':                                           ('TX - China Service Medal - Disabled',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-civil-air-patrol-texas-wing':                                            ('TX - Civil Air Patrol - Texas Wing',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-coast-guard-academy-disabled':                                           ('TX - Coast Guard Academy - Disabled',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-coast-guard-auxiliary':                                                  ('TX - Coast Guard Auxiliary',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-coast-guard-disabled':                                                   ('TX - Coast Guard - Disabled',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-coast-guard-medal':                                                      ('TX - Coast Guard Medal',                                                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-coast-guard-medal-disabled':                                             ('TX - Coast Guard Medal - Disabled',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-badge':                                                    ('TX - Combat Action Badge',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-badge-disabled':                                           ('TX - Combat Action Badge - Disabled',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-medal':                                                    ('TX - Combat Action Medal',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-medal-disabled':                                           ('TX - Combat Action Medal - Disabled',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-ribbon-coast-guard':                                       ('TX - Combat Action Ribbon - Coast Guard',                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-ribbon-coast-guard-disabled':                              ('TX - Combat Action Ribbon - Coast Guard - Disabled',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-ribbon-navy-and-marine-corp-disabled':                     ('TX - Combat Action Ribbon - Navy and Marine Corps - Disabled',                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-action-ribbon-navy-and-marine-corps':                             ('TX - Combat Action Ribbon - Navy and Marine Corps',                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-infantryman-badge':                                               ('TX - Combat Infantryman Badge',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-infantryman-badge-disabled':                                      ('TX - Combat Infantryman Badge - Disabled',                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-medical-badge':                                                   ('TX - Combat Medical Badge',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-combat-medical-badge-disabled':                                          ('TX - Combat Medical Badge - Disabled',                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-commendation-medal-coast-guard':                                         ('TX - Commendation Medal - Coast Guard',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-commendation-medal-for-joint-services':                                  ('TX - Commendation Medal for Joint Services',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-commendation-medal-w-valor-coast-guard':                                 ('TX - Commendation Medal w/ Valor - Coast Guard',                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-commendation-medal-w-valor-coast-guard-disabled':                        ('TX - Commendation Medal w/ Valor - Coast Guard - Disabled',                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-commendation-medal-w-valor-joint-services':                              ('TX - Commendation Medal w/ Valor - Joint Services',                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-commendation-medal-w-valor-joint-session-disabled':                      ('TX - Commendation Medal w/ Valor - Joint Services - Disabled',                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-defense-meritorius-service-medal-disabled':                              ('TX - Defense Meritorious Service Medal - Disabled',                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-defense-superior-service-medal':                                         ('TX - Defense Superior Service Medal',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-defense-superior-service-medal-disabled':                                ('TX - Defense Superior Service Medal - Disabled',                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-desert-storm-national-defense-service-medal':                            ('TX - Desert Storm - National Defense Service Medal',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-desert-storm-national-defense-service-medal-disabled':                   ('TX - Desert Storm - National Defense Service Medal - Disabled',               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-desert-storm-southwest-asia-service-medal':                              ('TX - Desert Storm - Southwest Asia Service Medal',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-desert-storm-southwest-asia-service-medal-disabled':                     ('TX - Desert Storm - Southwest Asia Service Medal - Disabled',                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-disabled-veteran':                                                       ('TX - Disabled Veteran',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguised-flying-cross-medal-disabled':                               ('TX - Distinguished Flying Cross Medal - Disabled',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguised-flying-cross-medal-w-valor-disabled':                       ('TX - Distinguished Flying Cross Medal w/ Valor - Disabled',                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-flying-cross-medal':                                       ('TX - Distinguished Flying Cross Medal',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-flying-cross-medal-w-valor':                               ('TX - Distinguished Flying Cross Medal w/ Valor',                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal':                                            ('TX - Distinguished Service Medal',                                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-air-force':                                  ('TX - Distinguished Service Medal - Air Force',                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-air-force-disabled':                         ('TX - Distinguished Service Medal - Air Force - Disabled',                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-army':                                       ('TX - Distinguished Service Medal - Army',                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-coast-guard':                                ('TX - Distinguished Service Medal - Coast Guard',                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-coast-guard-disabled':                       ('TX - Distinguished Service Medal - Coast Guard - Disabled',                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-department-disabled':                        ('TX - Distinguished Service Medal - Department - Disabled',                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-department-of-defense':                      ('TX - Distinguished Service Medal - Department of Defense',                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-department-of-homeland-security':            ('TX - Distinguished Service Medal - Department of Homeland Security',          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-department-of-transportation':               ('TX - Distinguished Service Medal - Department of Transportation',             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-Dept-homeland-security-disabled':            ('TX - Distinguished Service Medal - Dept. Homeland Security - Disabled',       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-disabled':                                   ('TX - Distinguished Service Medal - Disabled',                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-navy':                                       ('TX - Distinguished Service Medal - Navy',                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-distinguished-service-medal-navy-disabled':                              ('TX - Distinguished Service Medal - Navy - Disabled',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-enduring-freedom-afghanistan-disabled':                                  ('TX - Enduring Freedom - Afghanistan - Disabled',                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-global-war-on-terrorism-expeditionary-medal':                            ('TX - Global War on Terrorism - Expeditionary Medal',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-global-war-on-terrorism-expeditionary-medal-disabled':                   ('TX - Global War on Terrorism - Expeditionary Medal - Disabled',               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-global-war-on-terrorism-service-medal':                                  ('TX - Global War on Terrorism - Service Medal',                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-global-war-on-terrorism-service-medal-disabled':                         ('TX - Global War on Terrorism - Service Medal - Disabled',                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-gold-star-family':                                                       ('TX - Gold Star Family',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-gold-star-father':                                                       ('TX - Gold Star Father',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-gold-star-mother':                                                       ('TX - Gold Star Mother',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-gold-star-spouse':                                                       ('TX - Gold Star Spouse',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-honorably-discharged-us-coast-guard':                                    ('TX - Honorably Discharged - US Coast Guard',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-honorably-discharged-us-marine-corps':                                   ('TX - Honorably Discharged - US Marine Corps',                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-honorably-discharged-us-navy':                                           ('TX - Honorably Discharged - US Navy',                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-humanitarian-service-medal':                                             ('TX - Humanitarian Service Medal',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-humanitarian-service-medal-disabled':                                    ('TX - Humanitarian Service Medal - Disabled',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-inherent-resolve-campaign-medal':                                        ('TX - Inherent Resolve Campaign Medal',                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-inherent-resolve-campaign-medal-disabled':                               ('TX - Inherent Resolve Campaign Medal - Disabled',                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-korean-defense-service-medal':                                           ('TX - Korean Defense Service Medal',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-korean-defense-service-medal-disabled':                                  ('TX - Korean Defense Service Medal - Disabled',                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-korean-service-medal':                                                   ('TX - Korean Service Medal',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-korean-service-medal-disabled':                                          ('TX - Korean Service Medal - Disabled',                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-korean-war-national-defense-service-medal':                              ('TX - Korean War - National Defense Service Medal',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-korea-veteran-national-defense-service-medal-disabled':                  ('TX - Korea Veteran - National Defense Service Medal - Disabled',              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-kosovo-campaign-medal':                                                  ('TX - Kosovo Campaign Medal',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-kosovo-campaign-medal-disabled':                                         ('TX - Kosovo Campaign Medal - Disabled',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-legion-of-merit-disabled':                                               ('TX - Legion of Merit - Disabled',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-legion-of-merit-medal':                                                  ('TX - Legion of Merit Medal',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-legion-of-valor-air-force-cross-medal-disabled':                         ('TX - Legion of Valor - Air Force Cross Medal - Disabled',                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-legion-of-valor-distinguished-service-cross':                            ('TX - Legion of Valor - Distinguished Service Cross',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-legion-of-valor-navy-cross-medal-disabled':                              ('TX - Legion of Valor - Navy Cross Medal - Disabled',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-lone-star-distinguished-service-medal':                                  ('TX - Lone Star Distinguished Service Medal',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-lone-star-distinguished-service-medal-disabled':                         ('TX - Lone Star Distinguished Service Medal - Disabled',                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-marine-corps-disabled':                                                  ('TX - Marine Corps - Disabled',                                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-marine-corps-expeditionary-medal':                                       ('TX - Marine Corps Expeditionary Medal',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-marine-corps-expeditionary-medal-disabled':                              ('TX - Marine Corps Expeditionary Medal - Disabled',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-marine-corps-league':                                                    ('TX - Marine Corps League',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-master-army-aviator':                                                    ('TX - Master Army Aviator',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-master-paratrooper':                                                     ('TX - Master Paratrooper',                                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-master-paratrooper-disabled':                                            ('TX - Master Paratrooper - Disabled',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-medal-of-honor-air-force-disabled':                                      ('TX - Medal of Honor - Air Force - Disabled',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-medal-of-honor-navy-disabled':                                           ('TX - Medal of Honor - Navy - Disabled',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-merchant-marine':                                                        ('TX - Merchant Marine',                                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-merchant-marine-expeditionary-medal':                                    ('TX - Merchant Marine Expeditionary Medal',                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-merchant-marine-expeditionary-medal-disabled':                           ('TX - Merchant Marine Expeditionary Medal - Disabled',                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-merchant-marines-academy-disabled':                                      ('TX - Merchant Marines Academy - Disabled',                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-meritorious-service-medal':                                              ('TX - Meritorious Service Medal',                                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-meritorious-service-medal-defense':                                      ('TX - Meritorious Service Medal - Defense',                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-meritorious-service-medal-disabled':                                     ('TX - Meritorious Service Medal - Disabled',                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-military-outstanding-volunteer-service-medal':                           ('TX - Military Outstanding Volunteer Service Medal',                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-military-outstanding-volunteer-service-medal-disabled':                  ('TX - Military Outstanding Volunteer Service Medal - Disabled',                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-naval-academy-disabled':                                                 ('TX - Naval Academy - Disabled',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-and-marine-corps-achievement-meda':                                 ('TX - Navy and Marine Corps Achievement Medal',                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-and-marine-corps-commendation-medal':                               ('TX - Navy and Marine Corps Commendation Medal',                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-and-marine-corps-commendation-medal-w-valor':                       ('TX - Navy and Marine Corps Commendation Medal w/ Valor',                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-and-marine-corps-commendation-medal-w-valor-disabled':              ('TX - Navy and Marine Corps Commendation Medal w/ Valor - Disabled',           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-and-marine-corps-medal':                                            ('TX - Navy and Marine Corps Medal',                                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-and-marine-corps-medal-disabled':                                   ('TX - Navy and Marine Corps Medal - Disabled',                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-cross-medal':                                                       ('TX - Navy Cross Medal',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-disabled':                                                          ('TX - Navy - Disabled',                                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-expeditionary-medal':                                               ('TX - Navy Expeditionary Medal',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-expeditionary-medal-disabled':                                      ('TX - Navy Expeditionary Medal - Disabled',                                    CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-submarine-services-enlisted':                                       ('TX - Navy Submarine Services - Enlisted',                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-submarine-services-enlisted-disabled':                              ('TX - Navy Submarine Services - Enlisted - Disabled',                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-submarine-services-officer':                                        ('TX - Navy Submarine Services - Officer',                                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-navy-submarine-services-officer-disabled':                               ('TX - Navy Submarine Services - Officer - Disabled',                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-nuclear-deterrence-operations-service-medal':                            ('TX - Nuclear Deterrence Operations Service Medal',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-nuclear-deterrence-operations-service-medal-disabled':                   ('TX - Nuclear Deterrence Operations Service Medal - Disabled',                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-operation-enduring-freedom':                                             ('TX - Operation Enduring Freedom',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-operation-enduring-freedom-afghanistan-medal':                           ('TX - Operation Enduring Freedom - Afghanistan Medal',                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-operation-freedoms-sentinel':                                            ('TX - Operation Freedom\'s Sentinel',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-operation-freedoms-sentinel-disabled':                                   ('TX - Operation Freedom\'s Sentinel - Disabled',                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-operation-iraqi-freedom-disabled':                                       ('TX - Operation Iraqi Freedom - Disabled',                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-operation-iraqi-freedom-medal':                                          ('TX - Operation Iraqi Freedom Medal',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-paratrooper-disabled':                                                   ('TX - Paratrooper - Disabled',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-paratrooper-senior-disabled':                                            ('TX - Paratrooper - Senior - Disabled',                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-pearl-harbor-survivor':                                                  ('TX - Pearl Harbor Survivor',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-presidential-service-badge':                                             ('TX - Presidential Service Badge',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-presidential-service-badge-disabled':                                    ('TX - Presidential Service Badge - Disabled',                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-prisoner-of-war-disabled':                                               ('TX - Prisoner of War - Disabled',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-prisoner-of-war-medal':                                                  ('TX - Prisoner of War Medal',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-prisoner-of-war-medal-disabled-handicap':                                ('TX - Prisoner of War Medal - Disabled - Handicap',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-puple-heart-medal-disabled':                                             ('TX - Purple Heart Medal - Disabled',                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-purple-heart-recipient-medal':                                           ('TX - Purple Heart Recipient Medal',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-senior-paratrooper':                                                     ('TX - Senior Paratrooper',                                                     CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-silver-star-medal':                                                      ('TX - Silver Star Medal',                                                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-silver-star-medal-disabled':                                             ('TX - Silver Star Medal - Disabled',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-soldiers-medal':                                                         ('TX - Soldier\'s Medal',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-soldiers-medal-disabled':                                                ('TX - Soldier\'s Medal - Disabled',                                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-surviving-spouse-of-disabled-veteran':                                   ('TX - Surviving Spouse of Disabled Veteran',                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-homeland-defense-service-medal':                                   ('TX - Texas Homeland Defense Service Medal',                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-homeland-defense-service-medal-disabled':                          ('TX - Texas Homeland Defense Service Medal - Disabled',                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-humanitarian-service-medal':                                       ('TX - Texas Humanitarian Service Medal',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-humanitarian-service-medal-disabled':                              ('TX - Texas Humanitarian Service Medal - Disabled',                            CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-medal-of-merit':                                                   ('TX - Texas Medal of Merit',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-medal-of-merit-disabled':                                          ('TX - Texas Medal of Merit - Disabled',                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-national-guard':                                                   ('TX - Texas National Guard',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-outstanding-service-medal':                                        ('TX - Texas Outstanding Service Medal',                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-outstanding-service-medal-disabled':                               ('TX - Texas Outstanding Service Medal - Disabled',                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-superior-service-medal':                                           ('TX - Texas Superior Service Medal',                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-texas-superior-service-medal-disabled':                                  ('TX - Texas Superior Service Medal - Disabled',                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-tomb-guard':                                                             ('TX - Tomb Guard',                                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-air-force':                                                           ('TX - US Air Force',                                                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-air-force-academy':                                                   ('TX - US Air Force Academy',                                                   CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-air-force-retired':                                                   ('TX - US Air Force - Retired',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-usa-pride':                                                              ('TX - USA Pride',                                                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-army':                                                                ('TX - US Army',                                                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-army-retired':                                                        ('TX - US Army - Retired',                                                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-coast-guard':                                                         ('TX - US Coast Guard',                                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-coast-guard-academy':                                                 ('TX - US Coast Guard Academy',                                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-coast-guard-retired':                                                 ('TX - US Coast Guard - Retired',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-marine-corps':                                                        ('TX - US Marine Corps',                                                        CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-marine-corps-retired':                                                ('TX - US Marine Corps - Retired',                                              CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-merchant-marine-academy':                                             ('TX - US Merchant Marine Academy',                                             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-military-academy-west-point':                                         ('TX - US Military Academy - West Point',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-naval-academy':                                                       ('TX - US Naval Academy',                                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-navy':                                                                ('TX - US Navy',                                                                CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-navy-retired':                                                        ('TX - US Navy - Retired',                                                      CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-us-paratrooper':                                                         ('TX - US Paratrooper',                                                         CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-vietnam-service-medal':                                                  ('TX - Vietnam Service Medal',                                                  CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-vietnam-service-medal-disabled':                                         ('TX - Vietnam Service Medal - Disabled',                                       CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-vietnam-veteran-national-defense-service-medal-disabled':                ('TX - Vietnam Veteran - National Defense Service Medal - Disabled',             CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-vietnam-war-national-defense-service-medal':                             ('TX - Vietnam War - National Defense Service Medal',                           CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-west-point-military-academy-disabled':                                   ('TX - West Point Military Academy - Disabled',                                 CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-woman-veteran':                                                          ('TX - Woman Veteran',                                                          CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-woman-veteran-disabled':                                                 ('TX - Woman Veteran - Disabled',                                               CAT['Military / Veteran'], 90, TX_MILITARY),
        'tx-wwii-veterans-medal':                                                    ('TX - WWII Veterans Medal',                                                    CAT['Military / Veteran'], 90, TX_MILITARY),

        # ── tx-standard-issue ────────────────────────────────────────────────────────────────────
        'tx-standard-issue-1992-lone-star-state':    ('TX - Standard Issue - 1992 - Lone Star State',  CAT['Standard Issue'], 95, TX_STD_1992),
        'tx-standard-issue-2000-space-shuttle':      ('TX - Standard Issue - 2000 - Space Shuttle',    CAT['Standard Issue'], 95, TX_STD_2000),
        'tx-standard-issue-2009-lone-star':          ('TX - Standard Issue - 2009 - Lone Star',        CAT['Standard Issue'], 95, TX_STD_2009),
        'tx-standard-issue-2012-texas-classic':      ('TX - Standard Issue - 2012 - White',            CAT['Standard Issue'], 95, TX_STD_2012),

        # ── tx-first-responder ───────────────────────────────────────────────────────────────────
        'tx-blue-knights':                               ('TX - Blue Knights',                             CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-civil-air-patrol':                           ('TX - Civil Air Patrol',                         CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-disabled-peace-officer':                     ('TX - Disabled Peace Officer',                   CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-dps-troopers-foundation':                    ('TX - DPS Troopers Foundation',                  CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-emergency-medical-services-personnel':       ('TX - Emergency Medical Services Personnel',     CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-fallen-law-enforcement-officer':             ('TX - Fallen Law Enforcement Officer',           CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-fire-protection-personnel':                  ('TX - Fire Protection Personnel',                CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-industrial-fire-fighter':                    ('TX - Industrial Fire Fighter',                  CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-k9s4cops':                                   ('TX - K9s4Cops',                                 CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-k9s4kids':                                   ('TX - K9s4Kids',                                 CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-peace-officer':                              ('TX - Peace Officer',                            CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-peace-officer-purple-heart':                 ('TX - Peace Officer - Purple Heart',             CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-peace-officers-memorial-foundation':         ('TX - Peace Officers Memorial Foundation',       CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-professional-fire-fighter':                  ('TX - Professional Fire Fighter',                CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-retired-firefighter':                        ('TX - Retired Firefighter',                      CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-retired-peace-officer':                      ('TX - Retired Peace Officer',                   CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-star-of-texas-awardee':                      ('TX - Star of Texas Awardee',                   CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-support-your-sheriffs-office':               ('TX - Support Your Sheriff\'s Office',           CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-texas-constable':                            ('TX - Texas Constable',                          CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-texas-navy':                                 ('TX - Texas Navy',                               CAT['First Responder'], 90, TX_SPECIALTY),
        'tx-volunteer-firefighter':                      ('TX - Volunteer Firefighter',                    CAT['First Responder'], 90, TX_SPECIALTY),

        # ── tx-fraternal ───────────────────────────────────────────────────────────────────────
        'tx-alpha-kappa-alpha':                          ('TX - Alpha Kappa Alpha',                        CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-alpha-phi-alpha':                            ('TX - Alpha Phi Alpha',                          CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-american-legion':                            ('TX - American Legion',                          CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-delta-sigma-theta':                          ('TX - Delta Sigma Theta',                        CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-eastern-star':                               ('TX - Eastern Star',                             CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-kappa-alpha-psi':                            ('TX - Kappa Alpha Psi',                          CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-knights-of-columbus':                        ('TX - Knights of Columbus',                      CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-omega-psi-phi':                              ('TX - Omega Psi Phi',                            CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-phi-beta-sigma-v1':                          ('TX - Phi Beta Sigma - v1',                      CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-phi-beta-sigma-v2':                          ('TX - Phi Beta Sigma - v2',                      CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-rotary-international':                       ('TX - Rotary International',                     CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-sigma-gamma-rho-v1':                         ('TX - Sigma Gamma Rho - v1',                     CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-sigma-gamma-rho-v2':                         ('TX - Sigma Gamma Rho - v2',                     CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-texas-elks':                                 ('TX - Texas Elks',                               CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-texas-masons':                               ('TX - Texas Masons',                             CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-zeta-phi-beta':                              ('TX - Zeta Phi Beta',                            CAT['Fraternal / Civic'], 88, TX_SPECIALTY),

        # ── tx-outdoors ────────────────────────────────────────────────────────────────────────
        'tx-adopt-a-beach':                              ('TX - Adopt-A-Beach',                            CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-big-bend-fossil':                            ('TX - Big Bend - Fossil',                        CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-big-bend-national-park':                     ('TX - Big Bend National Park',                   CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-coastal-conservation-association':           ('TX - Coastal Conservation Association',         CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-ducks-unlimited-black':                      ('TX - Ducks Unlimited - Black',                  CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-ducks-unlimited-blue-heron':                 ('TX - Ducks Unlimited - Blue Heron',             CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-ducks-unlimited-classic':                    ('TX - Ducks Unlimited - Classic',                CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-ducks-unlimited-three-dogs':                 ('TX - Ducks Unlimited - Three Dogs',             CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-go-texan-agriculture-v1':                    ('TX - Go Texan Agriculture - v1',                CAT['Agricultural'], 90, TX_SPECIALTY),
        'tx-go-texan-agriculture-v2':                    ('TX - Go Texan Agriculture - v2',                CAT['Agricultural'], 90, TX_SPECIALTY),
        'tx-go-texan-agriculture-v3':                    ('TX - Go Texan Agriculture - v3',                CAT['Agricultural'], 90, TX_SPECIALTY),
        'tx-go-texan-agriculture-v4':                    ('TX - Go Texan Agriculture - v4',                CAT['Agricultural'], 90, TX_SPECIALTY),
        'tx-guadalupe-mountains-natl-park':              ('TX - Guadalupe Mountains National Park',        CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-houston-audubon-birds-and-habitat':          ('TX - Houston Audubon - Birds and Habitat',      CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-houston-livestock-show-and-rodeo':           ('TX - Houston Livestock Show and Rodeo',         CAT['Agricultural'], 90, TX_SPECIALTY),
        'tx-keep-texas-beautiful':                       ('TX - Keep Texas Beautiful',                     CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-love-honey-bees':                            ('TX - Love Honey Bees',                          CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-marine-mammal-recovery':                     ('TX - Marine Mammal Recovery',                   CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-master-gardener':                            ('TX - Master Gardener',                          CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-national-wild-turkey-foundation':            ('TX - National Wild Turkey Foundation',          CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-natural-texas':                              ('TX - Natural Texas',                            CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-protect-wild-animals':                       ('TX - Protect Wild Animals',                     CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-quail':                                      ('TX - Quail',                                    CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-recycle-texas':                              ('TX - Recycle Texas',                            CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-sand-dollar':                                ('TX - Sand Dollar',                              CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-san-jacinto-texas-historic-district':        ('TX - San Jacinto - Texas Historic District',    CAT['Historical / Commemorative'], 90, TX_SPECIALTY),
        'tx-save-texas-ocelots':                         ('TX - Save Texas Ocelots',                       CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-sea-turtle':                                 ('TX - Sea Turtle',                               CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-smokey-bear':                                ('TX - Smokey Bear',                               CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-sunflower':                                  ('TX - Sunflower',                                CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas811-call-before-you-dig':               ('TX - Texas 811 - Call Before You Dig',          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-diver':                                ('TX - Texas Diver',                              CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-master-naturalist':                    ('TX - Texas Master Naturalist',                  CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-bighorn-sheep':     ('TX - Texas Parks and Wildlife - Bighorn Sheep', CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-bluebonnet':        ('TX - Texas Parks and Wildlife - Bluebonnet',    CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-camping':           ('TX - Texas Parks and Wildlife - Camping',       CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-horned-lizard':     ('TX - Texas Parks and Wildlife - Horned Lizard', CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-hummingbird':       ('TX - Texas Parks and Wildlife - Hummingbird',   CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-largemouth-bass':   ('TX - Texas Parks and Wildlife - Largemouth Bass', CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-monarch-butterfly': ('TX - Texas Parks and Wildlife - Monarch Butterfly', CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-rattlesnake':       ('TX - Texas Parks and Wildlife - Rattlesnake',   CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-roadrunner':        ('TX - Texas Parks and Wildlife - Roadrunner',    CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-texas-rivers':      ('TX - Texas Parks and Wildlife - Texas Rivers',  CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-parks-and-wildlife-whitetail-deer':    ('TX - Texas Parks and Wildlife - Whitetail Deer', CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-trails':                               ('TX - Texas Trails',                             CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-trophy-hunters-association':           ('TX - Texas Trophy Hunters Association',         CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-urban-forestry-council':               ('TX - Texas Urban Forestry Council',             CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-texas-wildflowers':                          ('TX - Texas Wildflowers',                        CAT['Conservation / Environment'], 90, TX_SPECIALTY),
        'tx-trout-unlimited-guadalupe-river':            ('TX - Trout Unlimited - Guadalupe River',        CAT['Conservation / Environment'], 90, TX_SPECIALTY),

        # ── tx-specialty ────────────────────────────────────────────────────────────────────────
        'tx-4-h':                                        ('TX - 4-H',                                      CAT['Agricultural'], 88, TX_SPECIALTY),
        'tx-aerospace-commission':                       ('TX - Aerospace Commission',                     CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-a-fine-cause':                               ('TX - A Fine Cause',                             CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-amateur-radio-operator':                     ('TX - Amateur Radio Operator',                   CAT['Radio / Amateur Radio'], 90, TX_SPECIALTY),
        'tx-american-flag-1776':                         ('TX - American Flag 1776',                       CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-american-quarter-horse-association':         ('TX - American Quarter Horse Association',        CAT['Agricultural'], 88, TX_SPECIALTY),
        'tx-animal-friendly-v1':                         ('TX - Animal Friendly - v1',                     CAT['Conservation / Environment'], 88, TX_SPECIALTY),
        'tx-animal-friendly-v2':                         ('TX - Animal Friendly - v2',                     CAT['Conservation / Environment'], 88, TX_SPECIALTY),
        'tx-autism-awareness':                           ('TX - Autism Awareness',                         CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-be-a-blood-donor':                           ('TX - Be a Blood Donor',                         CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-big-brothers-big-sisters-v1':                ('TX - Big Brothers Big Sisters - v1',            CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-big-brothers-big-sisters-v2':                ('TX - Big Brothers Big Sisters - v2',            CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-boy-scouts':                                 ('TX - Boy Scouts',                               CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-breast-cancer-ribbon':                       ('TX - Breast Cancer Ribbon',                     CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-breast-cancer-ribbons':                      ('TX - Breast Cancer Ribbons',                    CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-buffalo-soldiers':                           ('TX - Buffalo Soldiers',                         CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-calvary-hill':                               ('TX - Calvary Hill',                             CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-casa-court-appointed-special-advocate':      ('TX - CASA - Court Appointed Special Advocate',  CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-childhood-cancer-awareness':                 ('TX - Childhood Cancer Awareness',               CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-choose-life':                                ('TX - Choose Life',                              CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-citrus-industry':                            ('TX - Citrus Industry',                          CAT['Agricultural'], 88, TX_SPECIALTY),
        'tx-college-for-all-texans':                     ('TX - College for All Texans',                   CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-conserve-water':                             ('TX - Conserve Water',                           CAT['Conservation / Environment'], 88, TX_SPECIALTY),
        'tx-cotton-boll':                                ('TX - Cotton Boll',                              CAT['Agricultural'], 88, TX_SPECIALTY),
        'tx-daughters-of-the-american-revolution':       ('TX - Daughters of the American Revolution',     CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-deaf-and-hard-of-hearing':                   ('TX - Deaf and Hard of Hearing',                 CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-deaf-driver-awareness':                      ('TX - Deaf Driver Awareness',                    CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-doctor-pepper':                              ('TX - Dr Pepper',                                CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-dont-tread-on-me-flag':                      ('TX - Don\'t Tread on Me Flag',                  CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-el-paso-mission-valley':                     ('TX - El Paso Mission Valley',                   CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-f-35-fighter-jet':                           ('TX - F-35 Fighter Jet',                         CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-family-first':                               ('TX - Family First',                             CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-fight-terrorism':                            ('TX - Fight Terrorism',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-ford-v1':                                    ('TX - Ford - v1',                                CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-ford-v2':                                    ('TX - Ford - v2',                                CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-fort-worth-zoo':                             ('TX - Fort Worth Zoo',                           CAT['Conservation / Environment'], 88, TX_SPECIALTY),
        'tx-freebirds-burritos':                         ('TX - Freebirds Burritos',                       CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-girl-scouts':                                ('TX - Girl Scouts',                              CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-god-bless-america':                          ('TX - God Bless America',                        CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-god-bless-texas':                            ('TX - God Bless Texas',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-ignite-steam-energy':                        ('TX - Ignite STEAM Energy',                      CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-in-god-we-trust':                            ('TX - In God We Trust',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-insure-texas-kids':                          ('TX - Insure Texas Kids',                        CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-juneteenth':                                 ('TX - Juneteenth',                               CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-keller-williams-realty':                     ('TX - Keller Williams Realty',                   CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-make-a-wish':                                ('TX - Make-A-Wish',                              CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-march-of-dimes':                             ('TX - March of Dimes',                           CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-mighty-fine-burgers':                        ('TX - Mighty Fine Burgers',                      CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-mothers-against-drunk-driving':              ('TX - Mothers Against Drunk Driving',            CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-native-texan':                               ('TX - Native Texan',                             CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-nurse-practitioners':                        ('TX - Nurse Practitioners',                      CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-organ-donor':                                ('TX - Organ Donor',                              CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-porsche-club-of-america':                    ('TX - Porsche Club of America',                  CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-read-to-succeed':                            ('TX - Read to Succeed',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-register-to-vote':                           ('TX - Register to Vote',                         CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-remax':                                      ('TX - RE/MAX',                                   CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-retired-teacher':                            ('TX - Retired Teacher',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-share-the-road':                             ('TX - Share the Road',                           CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-sickle-cell-disease-awareness':              ('TX - Sickle Cell Disease Awareness',            CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-space-shuttle-columbia':                     ('TX - Space Shuttle Columbia',                   CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-state-capitol':                              ('TX - State Capitol',                            CAT['Historical / Commemorative'], 88, TX_SPECIALTY),
        'tx-stop-child-abuse':                           ('TX - Stop Child Abuse',                         CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-stop-human-trafficking':                     ('TX - Stop Human Trafficking',                   CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-support-adoption':                           ('TX - Support Adoption',                         CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-take-care-of-texas':                         ('TX - Take Care of Texas',                       CAT['Conservation / Environment'], 88, TX_SPECIALTY),
        'tx-texans-conquer-cancer':                      ('TX - Texans Conquer Cancer',                    CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-texas-lions-camp':                           ('TX - Texas Lions Camp',                         CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-medical-center':                       ('TX - Texas Medical Center',                     CAT['Health & Awareness'], 88, TX_SPECIALTY),
        'tx-texas-music':                                ('TX - Texas Music',                              CAT['Arts / Culture'], 88, TX_SPECIALTY),
        'tx-texas-oil-and-gas':                          ('TX - Texas Oil and Gas',                        CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-our-texas-state-song':                 ('TX - Texas, Our Texas - State Song',            CAT['Arts / Culture'], 88, TX_SPECIALTY),
        'tx-texas-reads':                                ('TX - Texas Reads',                              CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-realtor-association':                  ('TX - Texas Realtor Association',                CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-roadhouse':                            ('TX - Texas Roadhouse',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-state-fair':                           ('TX - Texas State Fair',                         CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-state-rifle-association':              ('TX - Texas State Rifle Association',            CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-texas-teacher':                              ('TX - Texas Teacher',                            CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-united-we-stand':                            ('TX - United We Stand',                          CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-usa-pride-freedom':                          ('TX - USA Pride - Freedom',                      CAT['Other / Specialty'], 88, TX_SPECIALTY),
        'tx-ymca':                                       ('TX - YMCA',                                     CAT['Fraternal / Civic'], 88, TX_SPECIALTY),
        'tx-young-lawyers':                              ('TX - Young Lawyers',                            CAT['Other / Specialty'], 88, TX_SPECIALTY),

        # ── tx-sports (series 859 — assumed typo from user\'s "857") ─────────────────────────────────
        'tx-austin-fc':                                  ('TX - Austin FC',                                CAT['Sports Team'], 90, TX_SPORTS),
        'tx-dallas-cowboys-blue':                        ('TX - Dallas Cowboys - Blue',                    CAT['Sports Team'], 90, TX_SPORTS),
        'tx-dallas-cowboys-silver':                      ('TX - Dallas Cowboys - Silver',                  CAT['Sports Team'], 90, TX_SPORTS),
        'tx-dallas-cowboys-star':                        ('TX - Dallas Cowboys - Star',                    CAT['Sports Team'], 90, TX_SPORTS),
        'tx-dallas-mavericks':                           ('TX - Dallas Mavericks',                         CAT['Sports Team'], 90, TX_SPORTS),
        'tx-dallas-mavericks-crossover':                 ('TX - Dallas Mavericks - Crossover',             CAT['Sports Team'], 90, TX_SPORTS),
        'tx-dallas-stars':                               ('TX - Dallas Stars',                             CAT['Sports Team'], 90, TX_SPORTS),
        'tx-fort-worth-cats':                            ('TX - Fort Worth Cats',                          CAT['Sports Team'], 90, TX_SPORTS),
        'tx-houston-astros':                             ('TX - Houston Astros',                           CAT['Sports Team'], 90, TX_SPORTS),
        'tx-houston-dynamo':                             ('TX - Houston Dynamo',                           CAT['Sports Team'], 90, TX_SPORTS),
        'tx-houston-rockets':                            ('TX - Houston Rockets',                          CAT['Sports Team'], 90, TX_SPORTS),
        'tx-houston-texans-v1':                          ('TX - Houston Texans - v1',                      CAT['Sports Team'], 90, TX_SPORTS),
        'tx-houston-texans-v2':                          ('TX - Houston Texans - v2',                      CAT['Sports Team'], 90, TX_SPORTS),
        'tx-houston-texans-v3-htown':                    ('TX - Houston Texans - v3 - H-Town',             CAT['Sports Team'], 90, TX_SPORTS),
        'tx-i-d-rather-be-golfing':                      ('TX - I\'d Rather Be Golfing',                   CAT['Other / Specialty'], 88, TX_SPORTS),
        'tx-nascar-24':                                  ('TX - NASCAR - 24',                              CAT['Sports Team'], 90, TX_SPORTS),
        'tx-nascar-3':                                   ('TX - NASCAR - 3',                               CAT['Sports Team'], 90, TX_SPORTS),
        'tx-nascar-88':                                  ('TX - NASCAR - 88',                              CAT['Sports Team'], 90, TX_SPORTS),
        'tx-nascar-v1':                                  ('TX - NASCAR - v1',                              CAT['Sports Team'], 90, TX_SPORTS),
        'tx-olympic-spirit':                             ('TX - Olympic Spirit',                           CAT['Other / Specialty'], 88, TX_SPORTS),
        'tx-oympic-committee':                           ('TX - Olympic Committee',                        CAT['Other / Specialty'], 88, TX_SPORTS),
        'tx-pga-foundation':                             ('TX - PGA Foundation',                           CAT['Other / Specialty'], 88, TX_SPORTS),
        'tx-san-antonio-spurs':                          ('TX - San Antonio Spurs',                        CAT['Sports Team'], 90, TX_SPORTS),
        'tx-special-olympics':                           ('TX - Special Olympics',                         CAT['Other / Specialty'], 88, TX_SPORTS),
        'tx-texas-motor-speedway':                       ('TX - Texas Motor Speedway',                     CAT['Other / Specialty'], 88, TX_SPORTS),
        'tx-texas-rangers':                              ('TX - Texas Rangers',                            CAT['Sports Team'], 90, TX_SPORTS),
        'tx-texas-stars-hockey':                         ('TX - Texas Stars Hockey',                       CAT['Sports Team'], 90, TX_SPORTS),
        'tx-ufc':                                        ('TX - UFC',                                      CAT['Sports Team'], 90, TX_SPORTS),
    }

    if stem not in NAME_OVERRIDE:
        return None

    plate_name, cat_id, cat_conf, series = NAME_OVERRIDE[stem]

    return {
        'filename':      stem + '.png',
        'plate_name':    plate_name,
        'slug':          slug_from_name(plate_name),
        'category_id':   cat_id,
        'category_conf': cat_conf,
        'vehicle_class': 'Passenger',
        'series_id':     series['id'],
        'series_conf':   series['conf'],
        'region_id':     44,
        'notes':         [],
        'src_subfolder': '',
    }


# ── Preview table ─────────────────────────────────────────────────────────────
CAT_ID_TO_NAME = {v: k for k, v in CAT.items()}

SERIES_ID_TO_NAME = {
    618: 'CO 2000 Mountain',
    620: 'CO Specialty 2018',
    621: 'TN 2023 Specialty',
    622: 'TN 2011 Green Hills',
    636: 'TN 2022 TNVACATION',
    637: 'TN 2023 Dark Blue',
    641: 'TN 1994 Bicentennial',
    642: 'TN 2000 Sounds Good',
    643: 'FL Specialty',
    649: 'OR Specialty',
    651: 'KY Specialty',
    653: 'WA Specialty',
    654: 'WA Standard Issue',
    655: 'AB Standard Issue',
    656: 'AB Specialty',
    657: 'AK Standard Issue',
    658: 'AK Specialty',
    659: 'AL 2022 Beach',
    660: 'AL 2014 Pond',
    661: 'AL 2009 Sweet Home',
    662: 'AL 2002 Stars',
    663: 'AL Specialty',
    664: 'AR 2006 Diamond',
    665: 'AR 1996 Natural State',
    666: 'AR 1988 White-Red',
    667: 'AR 1978 Land of Opportunity',
    668: 'AR Non-Passenger',
    669: 'AR Specialty',
    670: 'AZ Specialty',
    671: 'AZ Non-Passenger',
    672: 'AZ 2008 Screened',
    673: 'AZ 1996 Embossed',
    674: 'AZ 1980 Red',
    676: 'BC Standard Issue',
    677: 'BC Specialty',
    678: 'BC Non-Passenger',
    679: 'CT 2000 Series',
    680: 'CT 1987 Series',
    681: 'DC Washington',
    682: 'DE Standard Issue',
    683: 'DE Specialty',
    684: 'DE Black and White Reissue',
    685: 'GA 2012 Peach State',
    686: 'GA 2012 Prestige',
    687: 'GA Specialty',
    688: 'GA Non-Passenger',
    689: 'IA 2018 Standard Issue',
    690: 'IA Specialty',
    691: 'ID 1991 Scenic',
    692: 'ID Specialty',
    693: 'IL 2017 Land Of Lincoln',
    694: 'IL Non-Passenger',
    695: 'IL Specialty',
    696: 'IN 2017 Covered Bridge',
    697: 'IN 2013 Bicentennial',
    698: 'IN 2008 Blue',
    699: 'IN 2003 Farm',
    700: 'IN 1998 Crossroads',
    701: 'IN Specialty',
    702: 'IN Non-Passenger',
    703: 'KS Std Issue 2007 Embossed',
    704: 'KS Std Issue 2019 Screened',
    705: 'KS Pers Issue 2020 Powering Future',
    706: 'KS Std Issue 2025 To The Stars',
    707: 'KS Pers Issue 2025 Flint Hills',
    708: 'KS Specialty',
    709: 'KS Non-Passenger',
    710: 'LA Standard Issue 2025 America 250',
    711: 'LA Standard Issue 2005 Pelican',
    712: 'LA Non-Passenger',
    713: 'LA Specialty',
    714: 'MA Standard Issue 1993 Spirit',
    715: 'MA Specialty',
    716: 'MA Non-Passenger',
    717: 'MB Standard Issue 1997',
    718: 'MB Specialty',
    719: 'MD Standard Issue 2016 Flag',
    720: 'MD Standard Issue 1986 Shield',
    721: 'MD Specialty',
    722: 'ME Standard Issue 1999 Chickadee',
    723: 'ME Standard Issue 2025 White',
    724: 'ME Specialty',
    725: 'ME Veteran',
    727: 'IL Veteran and Military',
    726: 'MI Standard Issue 2013 Pure Michigan',
    728: 'MI Standard Issue Alternatives',
    729: 'MI Non-Passenger',
    730: 'MI Veteran and Military',
    731: 'MI Specialty',
    732: 'MN Standard Issue 1987 Explore',
    733: 'MN White',
    734: 'MN Specialty',
    735: 'MN Veteran',
    736: 'MO Standard Issue 2018 Bicentennial',
    737: 'MO Military and Veteran',
    738: 'MO Specialty',
    739: 'MO Standard Issue 2008 Bluebird',
    740: 'MO Standard Issue 1997 Show-Me',
    741: 'MO Civic and Government',
    742: 'MS Standard Issue 2019 Gold Seal',
    743: 'MS Standard Issue 2024 Magnolia',
    744: 'MS Alternative Issue 2022 Blackout',
    745: 'MS Veteran and Military',
    746: 'MS Non-Passenger and Government',
    747: 'MS Specialty',
    748: 'MT Military and Veteran',
    749: 'MT Standard Issue 2010 Blue',
    750: 'MT Standard Issue 2006 Gold Font',
    751: 'MT Standard Issue 2000 Blue Font',
    752: 'MT Standard Issue 1991 White Font',
    753: 'MT Standard Issue 1989 Centennial',
    754: 'MT Specialty',
    756: 'NC Standard Issue 1982 First In Flight',
    757: 'NC Non-Passenger',
    758: 'NC Specialty',
    759: 'ND Standard Issue - 2015 - Legendary',
    760: 'ND Vintage',
    761: 'ND Alternative Issue - 2025 - Blackout',
    762: 'ND Specialty',
    763: 'NE Standard Issue - 2023 - Genius',
    764: 'NE Standard Issue - 2017 - Sesquicentennial',
    765: 'NE Standard Issue - 2011 - Meadowlark',
    766: 'NE Standard Issue - 2005 - Conestoga',
    767: 'NE Standard Issue - 2002 - Prairie River',
    768: 'NE Specialty',
    769: 'NE Military and Veteran',
    770: 'NE Non-Passenger and Governmental',
    771: 'NH Standard Issue - 1999 - Live Free or Die',
    772: 'NH Standard Issue - 2026 - Bicentennial',
    773: 'NH Non-Passenger and Government',
    774: 'NH Specialty',
    775: 'NJ Standard Issue - 1992',
    776: 'NJ Non Passenger',
    777: 'NJ Specialty',
    778: 'NJ Military and Veteran',
    779: 'NM Standard Issue - 1990 - Yellow',
    780: 'NM Alternative Issue - 2016 - Turquoise',
    781: 'NM Alternative Issue - 2010 - Centennial',
    782: 'NM Alternative Issue - 2017 - Chilies',
    783: 'NM Veteran and Military',
    784: 'NM Non-Passenger and Government',
    785: 'NM Specialty',
    786: 'NM Alternative Issue - 1999 - Balloon',
    787: 'NT Standard Issue - 2010 - Spectacular',
    788: 'NV Standard Issue - 2016 - Home',
    789: 'NV Standard Issue - 2001 - Sunset',
    790: 'NV Standard Issue - 1983 - Big Horn Sheep',
    791: 'NV Standard Issue - 1969 - Blue',
    792: 'NV Alternative Issue - 2024 - 1969 Blue Reissue',
    793: 'NV Military and Veteran',
    794: 'NV Specialty',
    624: 'NY Standard Issue - 2020 - Excelsior',
    625: 'NY Specialty - Excelsior',
    626: 'NY Standard Issue - 2010 - Empire Gold',
    796: 'NY Standard Issue - 2001 - Empire State',
    797: 'NY Non-passenger and Government - 2010 - Empire Gold',
    798: 'NY Non-passenger and Government - 2001 - Empire State',
    799: 'NY Non-passenger and Government - 2020 - Excelsior',
    800: 'NY Standard Issue - 1986 - Statue of Liberty',
    801: 'OH Standard Issue - 2021 - Sunrise',
    802: 'OH Standard Issue - 2013 - Pride',
    803: 'OH Standard Issue - 2008 - Beautiful',
    804: 'OH Specialty - Sunrise',
    805: 'OH Non-passenger and Government',
    806: 'OK Standard Issue - 2024 - Imagine That',
    807: 'OK Standard Issue - 2017 - Scissortail',
    808: 'OK Specialty',
    809: 'OK Military and Veteran',
    810: 'OK Non-passenger and Governmental',
    811: 'ON Standard Issue - 1995 - Yours to Discover',
    812: 'ON Specialty',
    814: 'RI Standard Issue - 2023 - Ocean',
    815: 'RI Alternative Issue - 1992 - Sailboat',
    816: 'RI Alternative Issue - 2023 - Shark',
    817: 'RI Specialty',
    818: 'RI Veteran',
    819: 'SC Standard Issue - 2016 - While I Breathe I Hope',
    820: 'SC Specialty',
    821: 'SC Personalized',
    822: 'SD Standard Issue - 2006 - Great Faces',
    823: 'SD Specialty 2016',
    824: 'SD Specialty White',
    825: 'SK All Plates',
    826: 'NL Standard Issue - 2007',
    827: 'NL Standard Issue - 2024',
    828: 'NS All Plates',
    829: 'PE Standard Issue',
    830: 'PE Alt Issue',
    831: 'Nunavut - 2012',
    832: 'Nunavut - 2025',
    833: 'UT Alt - Skier',
    834: 'UT Alt - Arches',
    835: 'UT Standard Issue - Centennial',
    836: 'UT Standard Issue - 1985 - Skier',
    837: 'UT Standard Issue - 1973 - UTAH',
    838: 'UT Specialty',
    839: 'VT Standard Issue',
    840: 'VT Specialty',
    841: 'WI Standard Issue - 1986 - Americas Dairyland',
    842: 'WI Alternative Series',
    843: 'WI Non-passenger and Governmental',
    844: 'WI Tribal Nations',
    845: 'WI Specialty',
    846: 'VA Standard Issue - 2014 - Virginia Is For Lovers',
    847: 'VA Non-passenger and Government',
    848: 'VA Specialty',
    849: 'WV Standard Issue - 1995 - Wild, Wonderful',
    850: 'WV Specialty',
    851: 'WY Standard Issue - 2025 - Prestige',
    852: 'WY Standard Issue - 2016 - Green River',
    857: 'TX Schools',
    858: 'TX Alternatives',
    859: 'TX Sports',
    860: 'TX Standard Issue - 1992 - Lone Star State',
    861: 'TX Standard Issue - 2000 - Space Shuttle',
    863: 'TX Standard Issue - 2009 - Davis Mountains',
    864: 'TX Standard Issue - 2012 - White',
    865: 'TX Military',
    866: 'TX Specialty',
}


def print_preview(rows: list):
    headers = ['Plate Name', 'Category (conf%)', 'Class', 'Series (conf%)', 'Flags']
    col_w = [len(h) for h in headers]

    data = []
    for r in rows:
        cat_str = f"{CAT_ID_TO_NAME.get(r['category_id'], 'NULL')} ({r['category_conf']}%)" \
                  if r['category_id'] else f"NULL ({r['category_conf']}%)"
        ser_str = f"{SERIES_ID_TO_NAME.get(r['series_id'], str(r['series_id']))} ({r['series_conf']}%)" \
                  if r['series_id'] else 'NULL'
        flags = '; '.join(r['notes']) if r['notes'] else ''
        row = [r['plate_name'], cat_str, r['vehicle_class'], ser_str, flags]
        data.append(row)
        for i, cell in enumerate(row):
            col_w[i] = max(col_w[i], len(cell))

    sep = '+' + '+'.join('-' * (w + 2) for w in col_w) + '+'
    fmt = '| ' + ' | '.join(f'{{:<{w}}}' for w in col_w) + ' |'

    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in data:
        print(fmt.format(*row))
    print(sep)
    print(f"\nTotal: {len(rows)} plates")


# ── Execute ───────────────────────────────────────────────────────────────────
def execute_import(rows: list, src_folder: str, existing_slugs: set):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    dest = Path(IMG_DEST)
    dest.mkdir(parents=True, exist_ok=True)

    inserted = 0
    skipped  = 0
    errors   = []

    for r in rows:
        # Assign unique slug
        final_slug = unique_slug(r['slug'], existing_slugs)
        if final_slug != r['slug']:
            print(f"  SLUG COLLISION: {r['slug']} → {final_slug}")
        existing_slugs.add(final_slug)

        # Copy image
        src_subfolder = r.get('src_subfolder', '')
        src_path = Path(src_folder) / src_subfolder / r['filename']
        dst_path = dest / r['filename']
        if not src_path.exists():
            errors.append(f"Source not found: {src_path}")
            skipped += 1
            continue
        if dst_path.exists():
            print(f"  IMAGE EXISTS (skip copy): {r['filename']}")
        else:
            shutil.copy2(str(src_path), str(dst_path))

        # Build SQL
        def sql_val(v):
            if v is None:
                return 'NULL'
            if isinstance(v, int):
                return str(v)
            escaped = str(v).replace("'", "''")
            return f"'{escaped}'"

        sql = (
            f"INSERT INTO plates "
            f"(name, slug, series_id, category_id, vehicle_class, image_filename, "
            f"is_active, updates_complete, created_at, updated_at) VALUES ("
            f"{sql_val(r['plate_name'])}, "
            f"{sql_val(final_slug)}, "
            f"{sql_val(r['series_id'])}, "
            f"{sql_val(r['category_id'])}, "
            f"{sql_val(r['vehicle_class'])}, "
            f"{sql_val(r['filename'])}, "
            f"1, 0, '{now}', '{now}');"
        )

        result = subprocess.run(
            [MYSQL_BIN, f'-u{DB_USER}', f'-p{DB_PASS}',
             '-h', DB_HOST, '-P', DB_PORT, DB_NAME, '-e', sql],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            errors.append(f"DB error for {r['plate_name']}: {result.stderr.strip()}")
            skipped += 1
        else:
            inserted += 1
            print(f"  ✓ {r['plate_name']}")

    print(f"\nDone. Inserted: {inserted}  Skipped/errors: {skipped}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Bulk import plate images into platetag_api.')
    ap.add_argument('state', choices=['tn', 'co', 'fl', 'or', 'ky', 'wa', 'ab', 'ak', 'al', 'ar', 'az', 'bc', 'ct', 'dc', 'de', 'ga', 'ia', 'id', 'il', 'in', 'ks', 'la', 'ma', 'mb', 'md', 'me', 'mi', 'mn', 'mo', 'ms', 'mt', 'nc', 'nd', 'ne', 'nh', 'nj', 'nm', 'nv', 'ny', 'oh', 'ok', 'on', 'pe', 'ri', 'sc', 'sd', 'sk', 'tx', 'ut', 'va', 'vt', 'wi', 'wv', 'wy'], help='State/province to import')
    ap.add_argument('--execute',        action='store_true', help='Copy images and insert DB records (default: dry run)')
    ap.add_argument('--min-confidence', type=int, default=70, metavar='N',
                    help='Min confidence %% to assign a field (default: 70)')
    ap.add_argument('--folder',         help='Override default image folder path')
    args = ap.parse_args()

    if args.state == 'tn':
        folder = args.folder or TN_FOLDER
        parse_fn = parse_tn
    elif args.state == 'co':
        folder = args.folder or CO_FOLDER
        parse_fn = parse_co
    elif args.state == 'or':
        folder = args.folder or OR_FOLDER
        parse_fn = parse_or
    elif args.state == 'ab':
        folder = args.folder or AB_FOLDER
        parse_fn = parse_ab
    elif args.state == 'nv':
        folder = args.folder or NV_FOLDER
        parse_fn = None  # flat-folder loop
    elif args.state in ('fl', 'ky', 'wa', 'ak', 'al', 'ar', 'az', 'bc', 'ct', 'dc', 'de', 'ga', 'ia', 'id', 'il', 'in', 'ks', 'la', 'ma', 'mb', 'md', 'me', 'mi', 'mn', 'mo', 'ms', 'mt', 'nc', 'nd', 'ne', 'nh', 'nj', 'nm', 'ny', 'oh', 'ok', 'on', 'ri', 'sc'):
        folder_map = {'fl': FL_FOLDER, 'ky': KY_FOLDER, 'wa': WA_FOLDER, 'ak': AK_FOLDER, 'al': AL_FOLDER, 'ar': AR_FOLDER, 'az': AZ_FOLDER, 'bc': BC_FOLDER, 'ct': CT_FOLDER, 'dc': DC_FOLDER, 'de': DE_FOLDER, 'ga': GA_FOLDER, 'ia': IA_FOLDER, 'id': ID_FOLDER, 'il': IL_FOLDER, 'in': IN_FOLDER, 'ks': KS_FOLDER, 'la': LA_FOLDER, 'ma': MA_FOLDER, 'mb': MB_FOLDER, 'md': MD_FOLDER, 'me': ME_FOLDER, 'mi': MI_FOLDER, 'mn': MN_FOLDER, 'mo': MO_FOLDER, 'ms': MS_FOLDER, 'mt': MT_FOLDER, 'nc': NC_FOLDER, 'nd': ND_FOLDER, 'ne': NE_FOLDER, 'nh': NH_FOLDER, 'nj': NJ_FOLDER, 'nm': NM_FOLDER, 'ny': NY_FOLDER, 'oh': OH_FOLDER, 'ok': OK_FOLDER, 'on': ON_FOLDER, 'ri': RI_FOLDER, 'sc': SC_FOLDER}
        folder = args.folder or folder_map[args.state]
        parse_fn = None  # multi-folder loop
    elif args.state == 'sd':
        folder = args.folder or SD_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'pe':
        folder = args.folder or PE_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'ut':
        folder = args.folder or UT_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'vt':
        folder = args.folder or VT_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'wi':
        folder = args.folder or WI_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'va':
        folder = args.folder or VA_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'wv':
        folder = args.folder or WV_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'tx':
        folder = args.folder or TX_FOLDER
        parse_fn = parse_tx
    elif args.state == 'wy':
        folder = args.folder or WY_FOLDER
        parse_fn = None  # multi-folder loop
    elif args.state == 'sk':
        folder = args.folder or SK_FOLDER
        parse_fn = None  # flat-folder loop
    else:
        folder = args.folder or FL_FOLDER
        parse_fn = None

    if not Path(folder).exists():
        print(f"ERROR: Image folder not found: {folder}", file=sys.stderr)
        sys.exit(1)

    # Parse all image files
    rows = []
    skipped_files = []
    if args.state in ('fl', 'ky', 'wa', 'ak', 'al', 'ar', 'az', 'bc', 'ct', 'dc', 'de', 'ga', 'ia', 'id', 'il', 'in', 'ks', 'la', 'ma', 'mb', 'md', 'me', 'mi', 'mn', 'mo', 'ms', 'mt', 'nc', 'nd', 'ne', 'nh', 'nj', 'nm', 'ny', 'oh', 'ok', 'on', 'ri', 'sc', 'sd', 'pe', 'ut', 'va', 'vt', 'wi', 'wv', 'wy'):
        parse_map = {'fl': parse_fl, 'ky': parse_ky, 'wa': parse_wa, 'ak': parse_ak, 'al': parse_al, 'ar': parse_ar, 'az': parse_az, 'bc': parse_bc, 'ct': parse_ct, 'dc': parse_dc, 'de': parse_de, 'ga': parse_ga, 'ia': parse_ia, 'id': parse_id, 'il': parse_il, 'in': parse_in, 'ks': parse_ks, 'la': parse_la, 'ma': parse_ma, 'mb': parse_mb, 'md': parse_md, 'me': parse_me, 'mi': parse_mi, 'mn': parse_mn, 'mo': parse_mo, 'ms': parse_ms, 'mt': parse_mt, 'nc': parse_nc, 'nd': parse_nd, 'ne': parse_ne, 'nh': parse_nh, 'nj': parse_nj, 'nm': parse_nm, 'ny': parse_ny, 'oh': parse_oh, 'ok': parse_ok, 'on': parse_on, 'ri': parse_ri, 'sc': parse_sc, 'sd': parse_sd, 'pe': parse_pe, 'ut': parse_ut, 'va': parse_va, 'vt': parse_vt, 'wi': parse_wi, 'tx': parse_tx, 'wv': parse_wv, 'wy': parse_wy}
        parse_multi = parse_map[args.state]
        seen_filenames: set = set()
        for subdir in sorted(Path(folder).iterdir()):
            if not subdir.is_dir():
                continue
            for f in sorted(subdir.iterdir()):
                if f.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                    continue
                if f.name in seen_filenames:
                    skipped_files.append(f"{subdir.name}/{f.name} (duplicate — skipped)")
                    continue
                seen_filenames.add(f.name)
                result = parse_multi(f.stem, subdir.name, f.name)
                if result is None:
                    skipped_files.append(f"{subdir.name}/{f.name}")
                    continue
                rows.append(result)
    elif args.state == 'nv':
        for f in sorted(Path(folder).iterdir()):
            if f.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                continue
            result = parse_nv(f.stem, f.name)
            if result is None:
                skipped_files.append(f.name)
                continue
            rows.append(result)
    elif args.state == 'sk':
        for f in sorted(Path(folder).iterdir()):
            if f.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                continue
            result = parse_sk(f.stem, f.name)
            if result is None:
                skipped_files.append(f.name)
                continue
            rows.append(result)
    else:
        for f in sorted(Path(folder).iterdir()):
            if f.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                continue
            result = parse_fn(f.stem)
            if result is None:
                skipped_files.append(f.name)
                continue
            rows.append(result)

    if not rows:
        print("No files to process.")
        sys.exit(0)

    if skipped_files:
        print(f"Skipped (unrecognized prefix): {', '.join(skipped_files)}\n")

    print(f"{'DRY RUN — ' if not args.execute else ''}Processing {len(rows)} files from:\n  {folder}\n")
    print_preview(rows)

    if not args.execute:
        print("\nRun with --execute to copy images and insert records.")
        return

    # Confirm before executing
    ans = input(f"\nInsert {len(rows)} records into {DB_NAME}? [y/N] ").strip().lower()
    if ans != 'y':
        print("Aborted.")
        return

    existing_slugs = fetch_existing_slugs()
    execute_import(rows, folder, existing_slugs)


if __name__ == '__main__':
    main()
