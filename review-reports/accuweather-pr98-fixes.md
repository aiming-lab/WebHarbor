# AccuWeather PR #98: local audit corrections

The September 16, 2026 corrections address all 13 findings from the GUI audit:
mobile header/flash and form layouts, menu/homepage destinations, radar legend,
overall AQI scale, forecast consistency, task wording, rubrics, deterministic
answer/state checks, navigation order, asset resolution and review documentation.

Task 8 now explicitly requests the selected alert types; task 17 explicitly asks
for the maximum temperature as well as its first hour and precipitation chance.
The verifier preserves exact database delta and catalog checks while rejecting
wrong units, city/value swaps, contradictions and false confirmations.

Validation completed locally:

- 20 fresh tasks completed through mouse/keyboard/scroll actions; all pass the
  official deterministic evaluator. 180 steps and 20 decoded GIFs are retained.
- 111 copied-evidence controls match expectations: 21 accepted, 90 rejected.
- 301 verifier tests and 5 asset pin tests pass, with no skips.
- Independent seed builds are byte identical within the local SQLite runtime;
  populated startup is a no-op and the forecast consistency checks pass.
- Full Docker build passes; all 29 sites are healthy and their homepages respond.
  AccuWeather runtime/seed hashes match after reset and restart. Forty files in
  the final image match the working checkout. The owned test container is stopped.

The build uses a scoped immutable asset pin for AccuWeather from HF PR #66
(`0a73c1c1ac2e47513389a8a1a67601f75c8c4150`), retaining the existing global pin for
the other sites. A later integration can consolidate this after validating the
merged dataset revision. No publication is part of these local corrections.

Local evidence: `.assets/reviews/pr98-fixes/REPORT.md`, `manifest.json`,
`task-00/` through `task-19/`, `controls/`, and build/reset logs. The original
`.assets/reviews/pr98-gui-audit/` is preserved. Preview: http://localhost:41024/;
report/GIF gallery: http://localhost:41199/. Preview account state is preserved.

Weather is synthetic and radar remains illustrative. Answer matching supports
documented prose/labels and tested paraphrases; it is not a general language
reasoner. The secondary LLM judge was not run because its API/model configuration
is absent. These checks are regression evidence, not a statistical grading error rate.

## Integration with main

The revised PR was integrated with main `5d7a4e8` in source commit `dc4c2c5`.
AccuWeather is appended at index 31 (`40031`); the existing 31 site ports remain
unchanged. Registries, Docker EXPOSE, task URLs and setup documentation agree on
32 sites. Both B&H and AccuWeather retain their Docker seed-generation steps.
The global HF pin is the merged `fa1e8a5b9e8e5d0e42764cd658825f4dea088d8f`;
AccuWeather retains its independently validated immutable pin above.

Integration checks completed:

- Fresh fetch and archive validation/extraction for all 32 sites.
- 301 verifier tests, including the generated seed check, and 8 asset-fetch
  tests pass. Tests cover global/scoped pins, overrides, missing archives and
  build-generated sites that still require downloaded media.
- All 20 original GUI runs pass the official evaluator from this checkout;
  the reviewed task wording/rubrics are unchanged, with only the task URL port
  updated. All application, template, CSS and verifier code matches the GUI audit.
- Full Docker build `webharbor:pr98-integrated` succeeds. Image ID:
  `sha256:5c3213fcffe8e3563851d8315cf170fffc280e32ab5d115e35fc57fffa358856`.
- All 32 sites are healthy and return homepage HTTP 200; 51 tracked AccuWeather
  files in the image match the integrated source.
- Task 6 was replayed on that image using the original 15 mouse/keyboard/resize
  actions. Seattle appears in Alice's Saved Locations, the official verifier
  passes, and a new GIF is retained. This is a scripted GUI regression, separate
  from the original audit. The evaluator requires an absolute run-directory path.
- Reset after that GUI mutation restores byte identity with the shipped seed;
  a process restart preserves it (`f280733ebf0ec2a5c8546c2c2dccaadce00d508214edaa98f68cbb89150b752c`).

Integration evidence is retained under `.assets/reviews/pr98-integration/` in
`WebHarbor-integrate-pr98`, including fetch/build logs, evaluator verdicts,
`docker-task-06/`, source hashes, health responses and reset hashes. The original
preview and GIF gallery remain in the separate `WebHarbor-pr98` worktree.
