# TED PR 65 — Main-agent trajectory and visual audit

Date: 2026-09-06. I reviewed the final Luna trajectories, every task’s before/after DB, recorded page feedback, and the saved screenshots. The primary audit treats the browser interaction as the source of truth and checks for direct URL shortcuts, incomplete state transitions, answer leaks, missing screenshots, and responsive overflow.

| Task | Audit result | What was checked |
|---:|---|---|
| 0 | **PASS** | Search → Anil Seth detail; 15-minute answer; Read-only; 3 viewports. |
| 1 | **PASS** | Search “future” (11 results) → Waymo detail → Alice save + note; State delta contains only intended Waymo save. |
| 2 | **PASS** | Search “design” (7 results) → Debbie TEDNext detail; 8 minutes; Correct solo talk selected; co-talk excluded. |
| 3 | **PASS** | Climate/Nature/Conservation playlist → qualifying Summit talk title; Verifier requires a qualifying title token. |
| 4 | **PASS** | Alice login → account newsletter topic conservation; Profile update persisted in DB. |
| 5 | **PASS** | Search “world” (19 results) → Malala detail; exact title; Detail page supplies title. |
| 6 | **PASS** | Search “climate” (6 results) → Kimiko detail/event; Event is page-grounded. |
| 7 | **PASS** | Alice login → Events → TED2026 registration; Registration added from seed state. |
| 8 | **PASS** | Search “change” (27 results) Alexi; “design” (7 results) Debbie; compare; Both details and durations recorded. |
| 9 | **PASS** | Search “health” (6 results) → Joy detail → Alice save + note; State delta contains intended note. |
| 10 | **PASS** | AI/Society playlist → Neal Katyal Supreme Court talk; Playlist and detail both opened. |
| 11 | **PASS** | Visible talks listing → TED2026 + max 20 → Maya detail; Verifier binds event/max query and exact listing path. |
| 12 | **PASS** | Alice account → remove one non-AI saved talk; Exactly one removed; OpenClaw retained. |
| 13 | **PASS** | Science topic → wine-tasting detail; Qian Janice Wang; Exact speaker check. |
| 14 | **PASS** | Search “technology” (17 results) → Riyad architecture detail; Speaker page-grounded. |
| 15 | **PASS** | Both music details → Turkana has more views; Comparison grounded on both pages. |
| 16 | **PASS** | Register new user → visible /talks listing → OpenClaw save → account; New-user DB row and saved row confirmed. |
| 17 | **PASS** | Events → TEDNext 2025; November 2025; Answer requires both month and year. |
| 18 | **PASS** | TED2026 + AI + max 20 → Peter/Anil details; exact difference; UI exposes exact counts 551,544 and 191,682. |
| 19 | **PASS** | TEDNext 2025 + culture + max 10 → Nayeema/Kate details; exact difference; UI exposes exact counts 554,563 and 203,431. |

## Findings resolved during review

- Added Tasks 18 and 19 as filtered, two-detail exact view-count comparisons.
- Reworked narrow queries for Tasks 1, 5, 6, 8, 9, and 14 to provide distractors and require selection.
- Task 2’s clean run was redone from seed after an earlier contaminated after-state.
- Task 8 was rerun with visible result selection for both talks after earlier incomplete/wrong-query attempts.
- Task 11 was rerun with an exact click from the filtered TED2026 listing; its verifier now binds event and max-duration query parameters.
- Task 16 was rerun with visible `/talks` listing navigation; its verifier now recognizes the exact listing path without confusing detail URLs.
- Tasks 18 and 19 now record exact comma-separated UI view counts; `views_label` exposes the public integer count needed for arithmetic.
- Earlier attempts remain under each task’s `attempt-*` directory where applicable; the final trajectory and screenshots identify the accepted run.

## Visual/runtime audit

The final evidence includes real TED imagery and populated cards/details. Captured viewport widths include 1440, 390, and 320 pixels; screenshots were checked for horizontal overflow using recorded scroll-width feedback and image dimensions. The standalone TED service remained healthy (`/_health`, 64 talks; `/` and `/talks` HTTP 200). A full local Docker smoke run also passed: the control plane was healthy, all 17 site ports returned HTTP 200, and TED reset produced matching instance/seed MD5s. Earlier source rebuild attempts encountered unrelated asset locks; the existing review image supplied the complete environment smoke test.
