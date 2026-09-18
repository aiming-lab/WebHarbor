# BabyCenter grading contracts

Run through `agent_demo/eval_judge.py --run_dir ABSOLUTE_RUN --verifier True`.
The run must contain `trajectory.json`, real PNG screenshots, `initial.db` and
`after.db`. The verifier never falls back to mutable live state.

Task goals are concise; a separate, compact answer-format paragraph in `ques`
explicitly requests JSON and lists the keys. It stays visible to any runner that
reads `ques` (not hidden in reviewer metadata or a new loader-specific field).
Field names carry the
entity/age relationship; numeric fields contain numbers, not sentences with
incidental matching digits. Date strings accept ISO and written dates, ranges
accept a two-number array or equivalent `18–22 weeks` notation, and short text
facts accept common equivalent phrasing. Ground truth stays in reviewer-only
`answers.py`, not in the task file. Duplicate JSON keys, extra fields, missing
fields, wrong types, contradictions and wrong facts fail closed.

The verifier checks three independent layers: the answer contract, navigation
to the requested sources, and the exact database delta. The nine expanded tasks
allow any browser route and source order that achieves their stated outcomes;
fixed search strings, filters and index-page visits are no longer required.
Task 0 still requires both rendered calculator results but allows one visit to
their shared guide and does not prescribe particular input/click events. Tasks 3 and 7 retain
their explicitly requested filter/search workflows. No minimum action count is
enforced. A homepage-only answer or missing source still fails.
Clicks can use the bundled agent's numeric `index` payload. Selectors and
reviewer-invented button labels are never required.

State tasks must end on `/account` with the correct email in final browser
observation evidence. The bundled agent writes `observed_text` on each step and
`final_observed_text` / `final_url` at completion. A browser QA recorder can supply
the same final visible text. This is observed UI evidence, not agent reasoning
or its final answer. Registration additionally validates the actual stored
password hash. Every unrelated row and field must remain unchanged.

Short-task revisions add comparisons or saved-item management for IDs
0, 1, 2, 4, 5, 6, 8, 9 and 11. All 15 tasks now use explicit answer fields.
Sourced guides are sparse: account/calculator pages distinguish completed
gestational weeks from the nearest linked checkpoint, as of 2026-05-29.
Task 1 calls its additional ability field `raking_other_motor`; the former
`month_6_other_motor` leaked the month the agent was asked to discover. Regrading
older evidence requires an explicitly labelled field-name migration, not a
claim that the older recording used the new prompt.

The seed migration runs at fetch/build time, never during normal HTTP startup.
HF PR #78 is merged and pinned at immutable revision
`8f3437ffa3b80c606687c49a5c5bbdf158f1c9ce`; the archive matches the reviewed
bytes. The tracked migration corrects its seed without repacking the bundle.
