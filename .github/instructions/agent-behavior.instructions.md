---
name: "Agent Behavior & Accountability"
description: "Core communication and accountability rules that apply to every agent and the default coding agent in the PlateTag project. Governs how agents handle errors, bad input, workflow mistakes, and user communication."
applyTo: "**"
---

# Agent Behavior & Accountability — PlateTag Project

## Project Scope — READ THIS FIRST

This instruction file governs work on the **active PlateTag project only**:
- `platetag-app` — React Native / Expo mobile app (Android + iOS)
- `platetag-api` — Laravel 11 backend API + Filament admin panel

**`plates_react` is a retired legacy project. It is off-limits.**
No agent, tool, or script may read from, write to, or reference `plates_react` in any active development context.
If asked to work on something that would require touching `plates_react`, stop and flag it.

### Pre-Work Checklist (enacted 2026-06-11)

**Before starting ANY task, check `platetag-docs/` FIRST:**
1. `STATUS_UPDATE_RULES.md` → Content Ownership Map
2. `PROJECT_BIBLE.md` → services, accounts, build state, tech stack
3. `AGENTS.md` → specialized agents available (e.g., `@Beta`, `@Audit`, `@Design`)
4. Relevant status file (`APP_STATUS.md`, `WEB_STATUS.md`, or `project-state.instructions.md`)

See `platetag-docs/AGENTS.md` Pre-Work Checklist section for full details.

---

## About the User

- Larry (he/him). First name is Larry. Majercin is his last name.
- Has no formal coding or software development background.
- Is intelligent, curious, and learns quickly when explained clearly.
- Does not know insider jargon, acronyms, or technical shorthand — define terms the first time they appear.
- Follows detailed step-by-step instructions well.
- Prefers direct, honest feedback — not softened, not over-praised.
- Will handle a maximum of **three action steps per reply**. After three steps, stop and wait for his response.
- Is the sole developer/owner of this project. There is no team.

---

## Step-Gated Execution — Mandatory (enacted 2026-06-05 after 10-hour governance session)

**Larry is a non-technical vibe coder. He cannot find or fix broken code. If an agent makes a mistake, the next agent must clean it up — but the goal is to never create the mess in the first place.**

There is no race. There is no deadline. There is only the requirement that every change is correct, stable, safe, and secure.

### The rule

Every multi-step task must be executed as a sequence of **gated steps**. Before executing any step, the agent must:

1. **State what the step will do** — in plain language, one sentence.
2. **State what success looks like** — what grep result, line count, file content, or output confirms the step worked.
3. **Execute the step.**
4. **Verify success before proceeding** — read the output, check the result, confirm it matches expectation. If it does not, stop and fix it before moving to the next step.
5. **Only then move to the next step.**

### What this looks like in practice

```
Step 1 of 3: Find the split point.
- Success: grep returns exact line number for the boundary marker.
[execute grep]
- Verified: "## 1. Backend" found at line 513. Proceeding.

Step 2 of 3: Append historical content to archive.
- Success: archive grows from 161 to ~500 lines, ends with "Earlier May 2026."
[execute append]
- Verified: archive now 500 lines. Last entry correct. Proceeding.

Step 3 of 3: Remove historical content from main file.
- Success: zero matches for "Filament 2FA" or "Build 41" in main file.
[execute removal]
- Verified: grep returned nothing. Archive link cleanly transitions to "## 1. Backend." Done.
```

### Why this rule exists (June 5, 2026 — archive split failure)

- Agent attempted a file split in one rapid burst: find, extract, create archive, swap files — all without checking any intermediate result.
- Split point was guessed using `---` separator instead of verified with grep for the actual next section header (`## 1. Backend`).
- Half the historical entries were left behind. Archive was incomplete. Agent called it done without verification.
- On retry with step-gating (grep → confirm → append → verify → remove → verify), the same task completed correctly in 3 verified steps.
- **The difference: each operation was its own gate. No step 2 until step 1 confirmed.**

### This applies to everything

- File edits, file splits, file creation
- Running terminal commands
- Writing code
- Deploying to production
- Any operation that mutates state

**Speed is not a virtue here. Correctness is the only metric.**

### Task completion means the change is LIVE

When a task involves production-facing files (backend controllers, Filament resources, routes, config, middleware), **the task is not complete until the files are deployed to production.** Editing a file locally and passing a lint check is a step — not the end state.

1. **State deployment status at completion.** "Files are ready locally. Deploying now" or "Files are ready locally. Deployment pending because [reason]." Never report a production-facing change as complete while files are still local.
2. **Never wait for the user to ask about deployment.** If deployment is the next logical step, state it and ask permission in the same breath: "5 files ready locally. Deploy to production now?"
3. **After deployment, verify the change is visible.** For Filament changes, ask the user to refresh production admin and confirm. For API changes, run a smoke test.

### The final gate — before calling anything done

**Ask: "Would Larry see this working if he opened the app, site, or admin panel right now?"** If the answer is no, the task is not complete. This one question catches the gap between "files are correct on disk" and "the change is live for the user." No rule can cover every scenario — this question does.

### Why this rule exists (June 5, 2026 — Options A/D deployment gap)

- Four Filament resource files + AdminPanelProvider were edited, linted, and reported as done.
- Deployment was never mentioned. The user discovered the gap by manually visiting production Filament and seeing none of the changes.
- The task was 80% complete (code correct, verified locally) but the final 20% (deploy + verify live) was silently omitted.
- **Correctness on disk is not correctness in production.**

---

## Rule-Enforcement Traceability — Mandatory (enacted 2026-06-05)

Every rule in this file and in `project-state.instructions.md` is a **Go / No-Go gate.** Rules are not suggestions, conventions, or best-effort guidelines. When a rule applies to a task, the agent must either obey it or stop.

### The rule

1. **Every rule is a gate.** If a rule says "do X before Y" and X is not done, Y does not proceed. There is no "I'll go anyway" option.
2. **Cite the rule when enforcing it.** When implementing code that enforces a documented rule (e.g., adding a Filament banner per the Content Editing Rule), state: "Per the Content Editing Rule (HARD, enacted 2026-06-05), adding the production warning banner." This proves the rule was consulted and actively applied.
3. **If a rule was missed, say so.** When reviewing work, flag any applicable rule that was not invoked: "The Mandatory Security Audit rule should have fired before editing `AdminPanelProvider.php`. I missed it."

### Why this rule exists (June 5, 2026 — Options A/B/C implementation oversight)

- Three options (Filament banner, pre-sync count comparison, diff preview) were implemented in code.
- Step-Gated Execution and Write Verification fired correctly.
- But the Content Editing Rule, Pre-Sync Verification Rule, and Mandatory Security Audit rule were never explicitly cited.
- The code enforces the rules — but an agent reading the implementation later has no traceability back to which rule drove which change.
- **Citing the rule during implementation creates a bidirectional chain: rule → code, code → rule.**

---

## Agent Routing — Non-Negotiable

**When Larry addresses a message to a named agent (`@Master`, `@Audit`, `@PM`, `@Design`, etc.), the default coding agent MUST invoke that agent immediately using `runSubagent` and stop. It must not begin the work itself first.**

### The exact rule

1. If the message contains `@AgentName`, the first action is `runSubagent` with the correct `agentName`. No file reads, no planning, no partial work beforehand.
2. The prompt passed to the subagent must match the user's actual request — do not expand, reframe, or add scope the user did not specify.
3. After the subagent returns, relay its output to Larry. Do not silently override or supplement it.

### Why this rule exists (May 9 + May 25, 2026 incidents)

- **May 9**: An agent acted on its own authority by running a banned script. Production database was wiped.
- **May 25**: Larry addressed `@Master` to update the Audit agent's md file. The default coding agent began reading files and doing the work itself. When corrected, it invoked Master but gave it an expanded directive that changed the scope to a full codebase audit — which was not requested.

Bypassing agent routing is not a minor lapse. It removes Larry's control over who does what, under what rules, with what scope. It must never happen.

### What "acting on your own" looks like — do not do these

- Reading implementation files when the user directed a named agent to do the work
- Starting the task before invoking the subagent
- Invoking the subagent but giving it a directive that adds scope, changes the task, or removes constraints the user set
- Doing part of the work yourself and routing the rest to the subagent

---

## Directness Over Appeasement

These rules are non-negotiable and apply to every agent.

### When Larry makes a mistake — say so immediately

- If a file, input, or approach is wrong or unrecoverable: say that first, clearly, before proposing alternatives.
- Do not attempt to patch a bad input without first telling him it is bad and why.
- Do not spend time diagnosing a doomed approach. If the root problem is clear, stop and report it.

**Wrong:** "I noticed a few issues. Let me try to work around them…"
**Correct:** "This cannot be used. Here's why, and here's what to do instead."

### Accountability applies to workflow errors too

- If Larry skips a documented step, name the skipped step and its consequence directly.
- If a prior decision from Larry is the root cause of a current problem, say so — with the specific decision and why it matters.

### No affirmations that mask a problem

- Do not praise input while knowing it will fail.
- Do not soften findings with "mostly fine" or "just a small issue" when the actual impact is significant.
- Keep error explanations short and factual: what is wrong, why it matters, what to do instead.

### No undisclosed assumptions (enacted 2026-06-06)

- If a proposed fix, diagnosis, or plan is based on an assumption rather than confirmed evidence, state that explicitly before proceeding.
- The required format: "This is an assumption, not confirmed. Confidence: X%." Do not skip the confidence estimate.
- Never present an assumption as a finding. A finding is something verified by evidence (log output, code read, test result). An assumption is a hypothesis.
- If asked for a confidence level, give a real number. Do not round up to seem more certain.
- If confidence is below 70%, do not implement the fix. Gather more evidence first and state what evidence is needed.

### When something cannot be fixed — stop

State clearly:
1. What the input or situation is
2. Why it cannot proceed
3. The single correct next action

Do not offer speculative workarounds that will also fail.

---

## Three Steps Maximum Per Reply

When giving Larry instructions to execute, deliver a maximum of three steps, then stop and wait.
This prevents confusion, allows questions, and ensures nothing gets skipped.

---

## Code Investigation — Must Read Source, Not Guess (enacted 2026-06-05 after double failure)

When asked whether a feature exists or is complete, **read the source code directly.** Do not rely on grep alone.

1. **Grep is a starting point, never a conclusion.**
2. **If grep returns nothing, broaden the search or read the file.**
3. **Never rely on secondary sources (PM output, status docs) without code verification.** Source code is truth.
4. **When reporting "not found," state what you searched for.**

### Why this rule exists (June 5, 2026 incident)
Account Deletion was reported as not built on mobile based on a narrow grep. The feature was fully present in `SettingsScreen.tsx` — a broader search confirmed it immediately.

---

## Build Review Gate — Web App (enacted 2026-06-14)

The Build Review Gate defined in `platetag-docs/AGENTS.md` applies to **all three platforms**, including the web app (`platetag-web`). It is not limited to mobile EAS builds.

| Change type | Required gate |
|---|---|
| New user-facing UI element, page, or flow | @Design review before code |
| Auth, accounts, payments, user data changes | @Audit review before code |
| Navigation fix, bug fix, config-only | No gate |

**No web code may be committed or pushed to Vercel when a required gate has not been cleared or explicitly waived by Larry.**

When a gate is waived by Larry, record this in the `WEB_STATUS.md` session entry: "@Design gate waived by Larry — reason: [reason]."

### Why this rule exists (2026-06-13 + 2026-06-14 incidents)

- **2026-06-13:** Country dropdown + MX region hide — user-facing UI shipped with no @Design review. Gate was in `AGENTS.md` but was never consulted for web work.
- **2026-06-14:** Breadcrumb nav — @Design gate was correctly flagged but was flagged at push time, after code was already written. Gate must fire before coding, not before pushing.
- The rule existed in `AGENTS.md` for mobile. It was silently assumed not to apply to web. That assumption was wrong.

---

## Web Deploy — Code and Docs Must Travel Together (enacted 2026-06-14)

**When code is pushed to `platetag-web` (triggering a Vercel deploy), `WEB_STATUS.md` must be updated and committed in the same push. Code and its session entry are one unit — they never ship separately.**

### The rule

1. **Before `git push`:** Write the `WEB_STATUS.md` session entry for what is shipping.
2. **Stage `WEB_STATUS.md`** in the same commit as the changed code files, or as a follow-up commit before the push.
3. **Never push with a dirty (uncommitted) `WEB_STATUS.md`.** Run `git status` after staging to confirm no docs are left unstaged.
4. **The session entry must include:** what shipped, files changed, commit hash (can be added after push), and gate status (@Design/@Audit invoked or waived).

### Why this rule exists (2026-06-13 incident)

- Three builds of search/country dropdown code were pushed to Vercel on 2026-06-13.
- `WEB_STATUS.md` was written locally but never staged or committed.
- The next session found it as a dirty uncommitted file — 3 builds behind the deployed code.
- **The gap: code and docs were treated as two separate tasks. They are one task.**

---

## Archive-First Bug Investigation (enacted 2026-06-05)

When debugging a bug, **search the project archive before searching the internet.** The same bug may have been encountered and fixed before — the answer may already exist in your own files.

### The rule

1. **Search the archive first.** Use `grep_search` or `semantic_search` with relevant keywords on `docs/APP_STATUS_ARCHIVE.md` and `docs/DECISION_LOG.md`. Do this before any internet search.
2. **If a match is found, read the full build entry.** Past entries often contain root cause analysis, attempted fixes that failed, and the final working solution with exact file names and code patterns.
3. **When a solution is adapted from the archive, credit it in the fix documentation.** The session entry or commit must include: `[Archive: Build XX — adapted from {description}]`. This builds a chain of provenance — future agents can trace the fix back to its origin.

### Future concern (tagged, not implemented)

As the archive grows across dozens of builds, keyword search may become noisy. An appendix or index mapping bug categories (crash, auth, offline, UI) to build numbers may be needed. This is noted but not built yet.

---

## Task Completion & Accountability (enacted 2026-06-05)

1. **Before marking a todo "completed," state exactly what was verified and how.** Partial work is never "completed."
2. **If a secondary task interrupts a primary task, return to the primary after the secondary finishes.** Ask: "Shall I continue X?"
3. **A multi-phase plan must complete all phases.** Skipped phases are "deferred," never "completed."
4. **The todo list is the source of truth for open items.** Update it after every task switch.

### Why this rule exists (June 5, 2026 incident)
A 4-phase audit was planned. Phase 1 was partially done, phases 2-4 skipped. All 4 were marked "completed." The user discovered the gap.

---

## Post-Build Project Review (Standing Rule)

**A full project review must be run at the conclusion of every build session or backend deployment, before closing out.**

> **The authoritative trigger table and full review checklist live in `platetag-docs/STATUS_UPDATE_RULES.md`. Read that file — it is the single source of truth.**

### Write verification (non-negotiable)
After writing to ANY status file, verify the write succeeded with a targeted grep. Never assume success.

### This is not optional
Skipping the review leaves agent guidance files stale and produces wrong PM/Audit recommendations.

---

## Status File Update — Triggered by Build Events or Tester Reports (Standing Rule)

**Any time a build is submitted OR Larry reports tester results, the agent must immediately update all status files before responding to anything else.**

### Trigger 1 — EAS build submitted
Immediately after `eas submit` completes successfully, update ALL of the following:
1. `platetag-app/docs/APP_STATUS.md` — new build number, submission date, EAS build IDs, next build number, add session entry.
2. `platetag-app/.github/instructions/project-state.instructions.md` — current state block: build number, status, next build number.
3. `platetag-api/.github/instructions/project-state.instructions.md` — mobile app line in current state, next build number.
4. `platetag-docs/PROJECT_BIBLE.md` — current build number + next build number in Section 13.
5. `/memories/platetag-project.md` — current state: build number, submission status, next build number.

**Cross-reference check:** After updating all five, verify items 2, 3, 4, and 5 all show the same next build number. If they differ, fix them before moving on.

### Trigger 2 — Larry reports tester results
Immediately when Larry says testers ran through the build and reports pass/fail, update ALL of the following:
1. `platetag-app/docs/APP_STATUS.md` — add tester-verified date and result to the build's session entry.
2. `platetag-app/.github/instructions/project-state.instructions.md` — update tester status in current state.
3. `/memories/platetag-project.md` — update current state with verified status.

### Do not wait to be asked
These updates happen automatically as part of completing the build or receiving the tester report. They are not optional and must not be deferred to "end of session."

---

## Build & Submit Failure Rule (enacted 2026-06-08)

**After any failed `eas build` or `eas submit` command, the agent must STOP and investigate before attempting a retry. No automatic second attempt.**

### The rule

1. **First failure = investigate immediately.** Do not retry the same command.
2. **Required investigation sources:** EAS.dev submission/build logs, App Store Connect, Google Play Console.
3. **Report the actual error to Larry before proposing any fix.**
4. **Get Larry's approval before rebuilding** — a failed submission may have consumed a build number.
5. **Never retry a submit without confirming the build number was not already consumed.**

### Why this rule exists (2026-06-08 — iOS Build 65 submission failure)
Apple accepted the Build 65 binary on the first attempt but EAS reported failure. Two retries were attempted before investigation. Build number 65 was consumed, requiring a fresh iOS build (number 66) and wasting EAS credits.

---

## Mandatory Security Audit Before Every EAS Build or Production Controller Deployment

**No `eas build`, `eas submit`, or direct production deployment of API controllers/routes may proceed without a completed Audit agent pass.**

### Rule
- Before every EAS build, invoke the **Audit agent** on all files changed since the last build.
- Before deploying any backend controller, route file, or middleware directly to production via `scp` or cPanel, invoke the **Audit agent** on those files.
- The audit must produce a per-file PASS/FAIL verdict and an overall GO / NO-GO.
- If the result is NO-GO, stop. Fix the findings, re-audit, then proceed.

### Scope for backend changes
- Any new or modified controller methods that accept user input or perform DB writes
- Any changes to `routes/api.php`
- Any new or modified middleware
- Any Eloquent model changes touching `$fillable`
- **Any Filament resource changes (pages, forms, tables, authorization, imports/exports)**

### What to pass to the Audit agent
1. Files changed since the last build/deployment
2. Description of what each change does
3. New endpoints added or removed
4. Whether `auth:sanctum` and rate limiting are in place for each mutating endpoint

---

## Threshold-Dependent Feature Rules (enacted 2026-06-14 after Build 68/69 nudge failure)

Any feature that triggers UI or behavior at a numeric threshold (plate count, sighting count, score, etc.) requires a mandatory pre-implementation data-source declaration.

### Rule 1 — Declare the data source before writing threshold logic

Before writing any code that compares a count to a threshold, explicitly state:
- **What data source provides the count** (e.g., local SQLite, remote API response, cached module-level value, AuthContext user field)
- **When that source is authoritative** (e.g., "local SQLite is correct after the user discovers a plate on this device")
- **When that source is wrong** (e.g., "local SQLite undercounts if the account was created on another device, admin-reset on the server, or restored from a backup")

If the source is wrong in any realistic scenario for this feature, choose a different source or confirm with Larry before proceeding.

### Rule 2 — Test scenario pre-flight before every preview build

Before requesting a device test, describe exactly how to set up the test state and flag any conditions that would cause a false failure. Example format:

> "Test account needs 35+ plates in **[specific data source]**. If the account was server-reset or set via admin, the nudge will not appear because local SQLite will be empty. Verify by [specific check]."

If the test setup is non-trivial, provide step-by-step instructions rather than assuming the tester will figure it out.

### Rule 3 — Never borrow a data source from nearby code without verifying it fits

Reusing a data source from adjacent code (e.g., `getDiscoveredPlateIds()` used in `atCap` logic) is not a justification for using it in new logic. For every new use:
1. Read the function definition and confirm what it actually queries
2. Confirm it returns authoritative data for the specific new scenario
3. If there is any doubt, state the doubt explicitly before implementing

### Why these rules exist (2026-06-14 incident)

Build 68 shipped a 35-plate upgrade nudge using `getDiscoveredPlateIds()` — local SQLite only. The test account had plates admin-reset on the server; local SQLite had a different count. The nudge never appeared. A second preview build was required. Each missed build costs ~$17.50 (EAS + AI charges). This failure was fully preventable by reading the data source definition before use.

**The pattern to avoid:** borrowing a data source from nearby code without verifying it is authoritative for the new use case.
