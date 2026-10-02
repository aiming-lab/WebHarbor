## Review — `united_airlines` (PR #276)

**Verdict: REQUEST CHANGES.**

PR #276 is closed and merged. This is a follow-up audit of the United implementation on main at `e5c899cd0ef3f3b9a664edb3099b98ef05c854fb`. I followed the repository's `review-env` checklist using a native Flask deployment and real Chromium interactions. The findings below describe the audited implementation.

### Issues (summary)

- **MAJOR**: My trips → Choose seats accepts **36E for both travelers** in one booking and persists both assignments.
- **MAJOR**: Automatic check-in selects the same first available seat for multiple unassigned travelers.
- **MAJOR**: A later traveler's invalid seat can leave an earlier traveler's change committed, producing a partial update after a failed submission.

### Mechanical checks: PARTIAL

- **Existing verifier unit tests: PASS.** `python -m unittest discover -s sites/united_airlines/verify/tests`: **10 passed**. This result covers the existing verifier tests only.
- **Byte-identical reset: UNVERIFIED.** Docker build, all-site health, authenticated control-plane reset, and reset-all were not executed because Docker is unavailable in this environment.

### Visual fidelity: PARTIAL

United pages were included in the **76 page/viewport combinations** checked across the three reviewed mirrors at 1440px and 768px. The sampled pages had no page-level overflow, broken rendered images, HTTP failures, or JavaScript page errors. Side-by-side comparison against the real upstream site remains unverified.

### Functional depth: FAIL

Chromium interactions created a two-traveler ORD → DEN booking, then followed My trips → Choose seats and selected **36E for both travelers**. The booking confirmation was `EDZGSM`; both passenger rows were persisted with seat `36E`. Browser interactions used the normal CSRF-enabled flow.

Additional checks found that automatic check-in chooses the same first available seat for each unassigned traveler. My trips also mutates earlier passenger rows before validating every traveler's choice: a later occupied-seat submission can leave an earlier traveler's change committed even though the overall submission fails.

These behaviors violate distinct-seat assignment within one booking and the expectation that a rejected seat-change submission leaves all passenger assignments unchanged.

### Task quality: PARTIAL

The complete **21-task** browser/verifier replay was not executed. The 10 existing verifier tests passed, but they do not establish end-to-end solvability, shortcut resistance, or task difficulty for the entire task set. The duplicate-seat and partial-update cases demonstrate invalid application states that still require explicit negative coverage.

### Required fixes before approval

1. **(MAJOR) Validate all effective seat assignments before mutation.** Check seat existence, occupied-seat conflicts, and uniqueness within the booking before changing any passenger row. Add a negative case for two travelers choosing 36E.
2. **(MAJOR) Reserve automatic choices for subsequent travelers.** Once a seat is selected for one traveler, exclude it from the remaining travelers' choices. Add a multi-traveler automatic check-in regression.
3. **(MAJOR) Make each seat-change submission atomic.** Apply and commit assignments only after every traveler has a valid choice. A later invalid seat must leave all passenger rows unchanged; cover this in both My trips and check-in.
4. **(Verification pending) Complete environment acceptance.** Run a fresh Docker build, authenticated reset/reset-all with byte-identical seed checks, and the complete 21-task browser/verifier replay. Complete the upstream visual comparison before declaring full review PASS.
