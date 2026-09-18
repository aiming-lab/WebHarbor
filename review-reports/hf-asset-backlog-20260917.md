# HF asset integration for previous reviews

The required assets for the already-merged CarMax, Recreation.gov,
BoardGameGeek and AccuWeather reviews are now merged into `ChilleD/WebHarbor`.
Code pins are consolidated onto immutable merged revision
`9d67d0088a7535e455a331a823b67e3a7d666161`.

| Site | Original HF PR | Archive change |
|---|---|---|
| Recreation.gov | [#8](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/8), merged | Existing reviewed bundle retained; tracked seed migration runs during fetch/build |
| CarMax | [#15](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/15), merged | Original contribution merged first, then [#95](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/95) adds 11 recovered photos |
| BoardGameGeek | [#25](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/25), merged | Existing reviewed bundle retained |
| AccuWeather | [#66](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/66), merged | Existing reviewed media retained; seed remains build-generated |

The earlier OSU, B&H and GOV.UK asset merges remain present and unchanged.
All 39 files from the previous HF main (including 36 archives) were preserved
byte-for-byte. The four originally absent archives are now on HF main.

CarMax's replacement archive has SHA-256
`274ac06abebf353ebb6561ab0647fed5c8a048916dd8867b9dfa951963a8d81d`.
It contains 770 managed members, adds exactly 11 photos, and preserves all
753 original files including the seed database. Each added photo matches
`sites/carmax/recovered_assets.json` and decodes successfully. These are sourced
model-year stock photos, not exact vehicle trim/color matches. Seven other
unavailable vehicle hero images remain explicit placeholders.

## Validation

- All five HF PR states and merged revisions independently verified.
- Uploaded CarMax archive downloaded again and checked against the local candidate.
- Fresh fetch/extraction for all 38 registered sites; all archive SHA-256 values
  match HF metadata at the merged revision.
- Recreation.gov's tracked migration is byte-idempotent after fetch.
- Full Docker build passed: local image `webharbor:hf-backlog-20260917`, ID
  `sha256:33e9a4af742814f9363eef46d8a205336b0d868176ccea7e4ad48d3df9c32793`.
- 38/38 sites healthy and 38/38 homepages HTTP 200, before and after reset-all.
- Synthetic mutation followed by reset restored byte-identical seeds for all four
  sites; restart and reset-all also preserved byte identity.
- 257 tracked runtime files across the four sites match the tested checkout.
- Tests: 8 asset-fetch, 16 CarMax, 7 Recreation.gov, 14 BoardGameGeek and 301
  AccuWeather tests passed (one initially skipped image-seed check was subsequently
  exercised against the actual Docker-generated seed; all 10 seed/helper tests
  passed without skips on that fixture). Python compilation and diff checks passed.
- All 11 recovered image URLs match their hashes and render in a real browser at
  1440px and 390px, with no image/HTTP/JavaScript errors or horizontal overflow.
  Desktop and mobile screenshots were spot-checked visually.
- CarMax tasks 12, 16 and 19 replayed through the UI against the fresh image:
  12 recorded steps each; all three official deterministic verifier results pass.
- The disposable test container was stopped and removed.

## Evidence and release scope

Local evidence is retained at
`/home/qianhuiwu/projects/WebHarbor/.assets/reviews/hf-backlog-20260917/`.
It includes original PR diffs, before/after HF inventories, archive fingerprints,
merge records, fetch/build logs, tests and browser screenshots. These paths are
local evidence, not public hosting.

The integration branch is `integrate/hf-asset-backlog`, based on GitHub main
`2206530e54fc1d0463502bfc49f165fe854c6c89`. Existing code contribution history is
unchanged. AGENTS.md now requires merging required HF assets, updating pins and
validating fresh builds before completing future code integrations.

Docker Hub publication and deployment are separate and were not performed.
Existing user previews are preserved. Browser replays are scripted regressions,
not independent LLM-agent trials; no secondary LLM judge was run.
