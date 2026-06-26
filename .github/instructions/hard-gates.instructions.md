---
name: "PlateTag Hard Gates"
description: "Slim always-on safety rules. Full governance in agent-behavior.instructions.md."
applyTo: "**"
---

# PlateTag Hard Gates — Always Active

## Absolute Bans
- `plates_react/tools/prod_sync.py` — PERMANENTLY BANNED. Wiped production DB 2026-05-09. Never execute.
- `plates_react/` — RETIRED. Off-limits. No reads, writes, or references.
- Never run `migrate:fresh` or `migrate:reset` on production.
- Never hard-delete plates — use `is_active = 0`.
- Never touch `users`, `user_discovered_plates`, `discovery_sessions` with the sync script.
- Never run `npm install` without `--ignore-scripts`. Never run `npm update` without Larry's explicit approval.
- `APP_DEBUG=false` must remain set in production `.env` at all times.

## Production Deployment Gate
- A task is not complete until the change is LIVE and verified. Files on disk ≠ done.
- Deploy backend controllers/routes only after Audit agent returns GO.
- After deploying: run smoke tests or ask Larry to confirm the change is visible.
- Ask before closing: "Would Larry see this working if he opened the app/admin panel right now?"

## Content Editing Gate
- Production Filament = light theme = READ ONLY for plates/series/regions/categories.
- Local WAMP Filament = dark theme = editing allowed.
- Never sync without pre-sync count comparison. Stop on any discrepancy.

## Database Rules
- Never run a migration on production without a verified backup on hand.
- Ownership check required before any mutation — users may only modify their own data.
- Never truncate `user_discovered_plates` without a documented backup.

## Local Migration Gate (HARD — enacted 2026-06-23)

**Every local migration is a production schema change.** The DB sync script (`sync_to_prod.ps1`) is a one-way street: local → production. There is no such thing as a migration that stays local. Any migration run on localhost will reach production on the next sync.

Before running `php artisan migrate` for any new migration file, ALL of the following must be confirmed:

1. **Audit agent review required.** The migration is treated as a production schema change. Invoke `@Audit` before running.
2. **API exposure check (mandatory).** For every new column added to a table that is returned by any API endpoint (`plates`, `series`, `regions`, `categories`, `users`, etc.): confirm the column is in `$hidden` on the Eloquent model, or confirm intentional exposure is documented.
3. **Reversibility check.** Verify the `down()` method correctly reverses the `up()`. A migration with a broken rollback is a production risk.
4. **Sync scope check.** Confirm whether the new columns should be included in the DB sync or excluded. The sync script truncates and re-imports — new columns on tables that ARE synced will be overwritten if the dump does not include them.

### Why this rule exists (2026-06-23 — tagger migration incident)
- Migration added `ai_detail`, `ai_tags`, `ai_reviewed` to the `plates` table.
- Classified as admin-only → no Audit gate triggered (correct classification, but incomplete reasoning).
- The API `show()` endpoint serializes the full Plate model. New columns were immediately exposed to mobile app and web app users.
- The exposure was caught during a post-implementation governance review — not before the migration ran.
- **A pre-migration Audit would have caught the `$hidden` gap in under 60 seconds.**

## Communication Rules
- Max 3 action steps per reply. Stop and wait for Larry's response before continuing.
- Never create a file without running `file_search` first.
- If message contains `@AgentName` — invoke that agent via `runSubagent` immediately. Do not start the work yourself.
- State assumptions explicitly: "Assumption, not confirmed. Confidence: X%." Do not implement below 70%.

## Pre-Work Checklist
Before any task: check `platetag-docs/` first.
1. `STATUS_UPDATE_RULES.md` → Content Ownership Map
2. `PROJECT_BIBLE.md` → services, accounts, build state
3. `AGENTS.md` → specialized agents available
4. `project-state.instructions.md` → current sprint/backend state

## Full Reference Files (read when needed — not auto-loaded)
- Full governance rules: `.github/instructions/agent-behavior.instructions.md`
- Full project state: `.github/instructions/project-state.instructions.md`
