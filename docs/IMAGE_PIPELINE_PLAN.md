# Image Processing Pipeline — Project Plan

**Created:** 2026-05-09  
**Status:** Planning / Pre-implementation  
**Owner:** Larry

---

## Goal

Build a repeatable, low-cost pipeline to convert raw "real plate" photos into
clean, brand-new-looking reference images suitable for the Platetag app.

---

## The Problem

- Raw photos have: scratches, rust, flash flare, registration stickers,
  mount hole damage, skew/perspective distortion, fading
- AI chat tools (MS Copilot) hallucinate plate details and inconsistently
  follow multi-step instructions
- Need GREAT + RELIABLE output, not just "mostly okay"

---

## Chosen Architecture — Three-Stage Pipeline

```
Raw plate photo (from DMV site, ALPCA, personal photo)
        │
        ▼
[STAGE 1 — Python/Pillow]         FREE — no API
  • Auto-crop to plate edges
  • Perspective/skew correction
  • Exposure normalization (flash flare, fading)
  • Color saturation boost
  • Output: corrected_<filename>.png

        │
        ▼
[STAGE 2 — Stability AI Inpainting API]   ~$0.003–0.01/plate
  • Uses mask TEMPLATES (created once per plate format)
  • Removes: registration stickers, mount hole damage,
    isolated rust patches, isolated scratches
  • Prompt: "clean metal plate surface, brand new, no damage"
  • Output: cleaned_<filename>.png

        │
        ▼
[STAGE 3 — Python/Pillow]         FREE — no API
  • Mask old serial number region (template-based)
  • Sample background color at serial position
  • Paint over old serial with matched background
  • Render new generic serial (ABC 123, 1ABC234, etc.)
    in correct font, weight, and position
  • Output: final_<filename>.png  →  uploads/plate/
```

---

## Why This Split

| Task | Best Tool | Why |
|------|-----------|-----|
| Skew, exposure, color | Pillow (Python) | Deterministic math — no AI needed |
| Sticker/rust/hole removal | Stability AI inpainting | Localized fix, cheap, templatable |
| Serial replacement | Pillow (Python) | Deterministic — zero hallucination risk |
| Whole-image cleanup | Stability AI img2img | For plates with widespread scratching |

---

## Mask Templates (Create Once, Reuse Forever)

Masks are black-and-white PNG files where **white = area to fix**.

Templates needed:

| Template Name | Covers |
|---------------|--------|
| `mask_passenger_sticker.png` | Sticker zone — upper-right corner, standard US passenger |
| `mask_passenger_holes.png` | 2 mount holes — left/right center |
| `mask_motorcycle_holes.png` | Motorcycle plate hole positions |
| `mask_commercial_holes.png` | Commercial plate hole positions |

Additional templates added as new plate formats are encountered.

---

## API Choice: Stability AI (Primary)

**Why Stability over Firefly API:**
- No minimum credit purchase
- ~$0.003–0.01/plate vs Firefly's ~$0.05–0.08/plate
- Good enough quality for cleanup tasks
- Simpler API call structure

**Adobe Firefly API (Secondary/Upgrade path):**
- Use for high-importance showcase plates where quality is paramount
- Same Firefly engine as Photoshop Generative Fill
- Requires Adobe developer account + credit pack (~$20 minimum)
- Adobe Developer Console: https://developer.adobe.com/firefly-api/

---

## Cost Estimate

| Volume | Stability AI cost | Firefly API cost |
|--------|-------------------|------------------|
| 10 plates | ~$0.10 | ~$0.80 |
| 100 plates | ~$1.00 | ~$8.00 |
| 1,000 plates | ~$10.00 | ~$80.00 |

Existing 8K+ library does NOT need reprocessing through this pipeline
(Vision API tagging run handles those). Pipeline is for **new incoming plates**.

---

## Scripts To Build

- [ ] `tools/plate_prep.py` — Stage 1: Pillow corrections (skew, exposure, color)
- [ ] `tools/plate_clean.py` — Stage 2: Stability AI inpainting (stickers, holes, rust)
- [ ] `tools/plate_serial.py` — Stage 3: Serial number replacement
- [ ] `tools/plate_pipeline.py` — Orchestrator: runs all 3 stages on a folder of inputs
- [ ] `tools/masks/` — Directory for reusable mask template PNGs

---

## Stability AI Setup (To Do)

1. Create account at: https://platform.stability.ai/
2. Add payment method (no minimum, pay-as-you-go)
3. Generate API key
4. Store key in `tools/.env` as `STABILITY_API_KEY=...`
5. Install SDK: `pip install stability-sdk` or use raw `requests`

---

## MS Copilot Instruction File

The instruction file `graphic-plate-remiage-instructions-for-copilot.md` (on Desktop)
remains useful as a **fallback** when doing one-off manual cleanup for complex plates
before Stage 2 scripting is complete.

---

## Open Questions / Roadblocks

- Font matching for serial replacement: need to identify the font used per state/plate type.
  Most US plates use Highway Gothic or a close variant. May need a font file.
- Perspective correction requires knowing the 4 corners of the plate — may need
  a simple interactive "click the 4 corners" helper for the first run on each source image.
- Stage 2 quality on heavily rusted plates: unknown until tested. May fall back to
  manual Photoshop for severe cases.

---

## Related Files

- `docs/PLATE_IMPORT_WORKFLOW.md` — overall plate import process
- `tools/.env` — API keys (gitignored)
- `tools/tag_plates.py` — Vision API tagging (separate pipeline)
- `uploads/plate/` — final plate images served by the app
