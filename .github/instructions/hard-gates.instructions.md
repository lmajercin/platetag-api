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
