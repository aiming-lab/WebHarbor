## Review — `ups` (PR #275)

**Verdict: REQUEST CHANGES.**

PR #275 is closed and merged. This is a follow-up audit of the UPS implementation on main at `e5c899cd0ef3f3b9a664edb3099b98ef05c854fb`. I followed the repository's `review-env` checklist using a native Flask deployment and real Chromium interactions. The findings below describe the audited implementation.

### Issues (summary)

- **MAJOR**: The visible pickup wizard accepts a reversed window, such as September 30, 2026, **5:00 PM–12:00 PM**, and persists it in `pickup_requests`.
- **MAJOR**: Equal start/end times and malformed submitted time values can advance to review.
- **MAJOR**: Final submission does not revalidate the saved schedule before creating the pickup.

### Mechanical checks: PARTIAL

- **Existing verifier unit tests: PASS.** `python -m unittest discover -s sites/ups/verify/tests`: **10 passed**. This result covers the existing verifier tests only.
- **Byte-identical reset: UNVERIFIED.** Docker build, all-site health, authenticated control-plane reset, and reset-all were not executed because Docker is unavailable in this environment.

### Visual fidelity: PARTIAL

UPS pages were included in the **76 page/viewport combinations** checked across the three reviewed mirrors at 1440px and 768px. The sampled pages had no page-level overflow, broken rendered images, HTTP failures, or JavaScript page errors. Side-by-side comparison against the real upstream site remains unverified.

### Functional depth: FAIL

Chromium interactions followed Schedule a Pickup → Pickup Address → Package Details → Date & Time → Review → Schedule Pickup. Selecting September 30, 2026, with **5:00 PM** as the earliest time and **12:00 PM** as the latest time reached confirmation. The resulting SQLite row contained `2026-09-30`, `5:00 PM`, and `12:00 PM`.

This is an invalid pickup window accepted through the visible dropdowns and persisted by the normal CSRF-enabled flow. Additional negative submissions showed that equal times and malformed non-empty time values can also advance to review. The final submission lacks a second schedule-validation check before the database insert.

### Task quality: PARTIAL

The complete **20-task** browser/verifier replay was not executed. The 10 existing verifier tests passed, but they do not establish end-to-end solvability, shortcut resistance, or task difficulty for the entire task set. The scheduling defect also shows that the application can persist an invalid business state despite the existing verifier tests passing.

### Required fixes before approval

1. **(MAJOR) Validate the pickup window as times.** Parse AM/PM values and require the latest pickup time to be strictly later than the earliest time. Reject reversed, equal, or malformed values and add negative regression cases.
2. **(MAJOR) Keep invalid schedules on the Date & Time step.** Show a validation error and preserve the submitted values so the user can correct them.
3. **(MAJOR) Revalidate immediately before writing the pickup.** Validate the saved schedule at final submission before inserting `pickup_requests`; add a negative case for an invalid saved schedule.
4. **(Verification pending) Complete environment acceptance.** Run a fresh Docker build, authenticated reset/reset-all with byte-identical seed checks, and the complete 20-task browser/verifier replay. Complete the upstream visual comparison before declaring full review PASS.

## Follow-up implementation

The original audit above describes the pre-fix snapshot. The continuation adds
shared schedule validation at both Date & Time and final submission: only the
mirror's offered dates and times are accepted, and the latest time must be
strictly later than the earliest. Invalid submissions retain their values on
Date & Time and create no pickup. Regression cases cover reversed/equal times,
malformed or missing values, invalid saved sessions, and correcting a rejected
window, including the AM/noon boundary.

This is a focused handler regression review. Existing task definitions, rubrics,
verifiers, and HF archives are unchanged. Browser evidence and the combined
build/reset results are recorded in the PR description and external review
artifacts; the original full-site/upstream review limitations remain explicit.
