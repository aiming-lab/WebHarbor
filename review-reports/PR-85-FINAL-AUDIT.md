# PR #85 independent review and remediation audit

## Scope

This audit reviewed GitHub PR #85 head `18fa53a96b6131af0364f00aa2cbd07609a902c3` against base `90afddb6d4af382935ded9a385f2eead604188cf`. Seven independent review contexts assessed the pristine original head. Their raw reports are retained outside the repository under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr85-agents/reports-original-final/`.

## Review-agent findings and dispositions

| Review agent | Primary findings on the original head | Verification and disposition |
|---|---|---|
| Security | Hard-coded Flask secret, open redirects after login/save, no CSRF protection, GET logout, and default/weak registration password behavior. | Confirmed directly in the original `sites/ted/app.py` and templates. Fixed with an environment/random secret, strict local-path redirects, Flask-WTF CSRF, POST logout, session rotation, request/field limits, and server-side registration validation. HTTP regression tests cover CSRF, redirect rejection, credential non-disclosure, invalid registration, and safe GET behavior. |
| Tasks and data | Exact duration/view arithmetic and seed account state were correct; TED task URLs were all `40016`; task 12 allowed multiple valid non-AI choices; playlist membership required independent confirmation. | Data facts were verified from the downloaded SQLite seed. The integration review established that TED is site index 19 and therefore port `40019`; all 20 task URLs were corrected. Task 12 now reports the exact removed title while still accepting any one valid non-AI row through a database-bound verifier. Playlist ordering and membership were checked directly. `judge_rubric` is not included in the web-agent prompt: `agent_demo/agent.py` passes only `ques` to `build_messages` and carries the rubric solely into judge input. |
| Verifiers | LLM checks became implicit passes under `--no_llm`; URL checks used substrings without origin/path/query binding; several required search/topic/filter steps were unenforced; multiple answers were unbound or negation-sensitive; state checks were incomplete. | All 20 verifiers and `verify_lib.py` were replaced with deterministic same-origin path/query/order checks, click/submit/input checks, exact task identity, non-empty answers, negation-aware fact binding, complete read-only database comparison, and exact global state-table deltas. Positive, answer-only, wrong-task, external-origin, missing-filter, negated-answer, swapped-value, wrong-removal, unrelated-mutation, and same-table-extra-mutation tests pass. |
| UI, responsive, accessibility | Cards and the lead story hid talk titles; the stacked mobile header remained sticky; controls lacked labels; repeated event buttons lacked event-specific accessible names; talk images had empty alt text; focus styles were absent; footer alignment was poor on mobile. | Talk and lead cards now render titles and speakers, the mobile header is static, filters and note/search fields are labeled, event buttons carry event-specific accessible names, talk images have descriptive alt text, focus-visible styles are present, and mobile footer alignment is corrected. Automated 320 px, 390 px, and 1440 px checks cover 30 route/viewport combinations with no horizontal overflow or broken images. |
| Integration and assets | The original HF main pin did not contain `ted.tar.gz`; all tasks targeted IKEA's `40016`; docs still described 19 sites and ended at `40018`; committed smoke/HF/PR evidence was stale; runtime startup could manufacture a mutable seed and mask missing assets. | HF dataset PR #2 was merged and the repository-wide pin now references merge commit `480c892e976bada6c0ea3f5a66e2b9efda65525d`, which contains all 20 tarballs. The temporary TED override was removed. Full 20-site asset fetch and clean Docker build pass. Site registration and docs now use 20 sites and ports `40000-40019`. Runtime fails closed when the TED seed is absent and only copies the authoritative seed into `instance`. Stale PR-65 evidence was removed and replaced by this exact-head audit. |
| Application and data model | Runtime seed creation was nondeterministic and could mutate `instance_seed`; partial seed gates were unsafe; topic matching was case-sensitive; search was brittle for simple morphology; registration accepted invalid/default credentials; CSRF and secret handling were unsafe; legacy SQLAlchemy lookup was used. | Runtime seed generation was removed; startup requires the HF seed. Topic matching is case-insensitive, duration filtering uses exact seconds, and search accepts simple prefixes/plurals. Registration validation, CSRF, secret handling, foreign-key enforcement, unique indexes, duplicate-race handling, and SQLAlchemy 2 lookup are implemented. The TED seed migration is idempotent and adds unique saved-talk and registration indexes. |
| Evidence quality | The PR-authored evidence described PR #65, an older head, 17-site/old-port smoke output, a different HF revision, and a pre-existing image rather than a clean PR #85 source build. | All stale evidence files were removed. Current evidence includes reproducible unit/adversarial tests, actual browser trajectories with initial/after databases and verifier JSON, responsive screenshots/results, immutable asset download logs, a clean local image build, 20/20 site health, TED reset hash identity, and reset-all success. |

## Task validation

All 20 tasks were completed through the rendered UI from a fresh seed database. Each generated trajectory was evaluated by its corresponding deterministic verifier using the captured initial and after-state databases. Result: `20/20 PASS`.

The complete local browser evidence is retained under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr85-fixes/e2e/`. Responsive results and screenshots are retained under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/pr85-fixes/responsive/`.

## Repository and container validation

- Python compilation, shell syntax, Ruff fatal/undefined-name checks, and `git diff --check`: PASS.
- TED HTTP/app, verifier, migration, and environment regression suite: 27 tests PASS.
- All TED templates and all 64 talk details render successfully: PASS.
- Immutable TED asset fetch plus all-site asset fetch: PASS; 20 tarballs extracted.
- TED migration: creates two unique indexes on first application and zero on the second application.
- Clean Docker build from the remediated source tree: PASS (`sha256:212755ac90732a0a031cd997dc764eec39879efc97241a8809860f0d8b184e11`).
- Control-plane health and all 20 site roots: PASS.
- `/reset/ted`: PASS and runtime/seed SHA-256 values match.
- `/reset-all`: PASS for all 20 sites.

## Asset status

Hugging Face dataset PR #2 was merged as `480c892e976bada6c0ea3f5a66e2b9efda65525d`. The repository-wide asset pin now references that merge commit, which contains all 20 tarballs including `ted.tar.gz`; the temporary TED-specific override has been removed.
