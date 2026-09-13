# FedEx mirror scope

The homepage is based on the US FedEx homepage observed in Chrome on September 10, 2026. The image and font sources and checksums are recorded in `homepage-assets.json` and `asset_inventory.json`; the media itself ships in the paired Hugging Face asset archive and is never committed to Git. Desktop and mobile use their respective original hero images. No live scripts, trackers or remote media requests are needed by the mirror, and no page references a remote origin.

Third-party material, including the two FedEx Sans web fonts and their embedded copyright and licence records, is dispositioned in `NOTICE.md`.

## Offline boundaries

Tracking, rates, locations, support, local accounts, shipment creation and pickup scheduling are benchmark workflows backed by deterministic local records. They do not contact FedEx, purchase shipping, or create real carrier bookings. The support detail pages explicitly distinguish local guidance from carrier policy.

Marketing, printing, sweepstakes, refunds, corporate links, social links and app downloads preserve their homepage entry points but open an offline-availability notice. Those live workflows are not implemented. Fonts include original regular and light weights; the browser synthesizes bold.

Two brand color pairings are deliberately adjusted for contrast, which is a documented departure from the source palette. Action surfaces and labels use `#ba4b00` instead of the original `#f60` (2.936:1 with white at 16px/700). White labels on the action orange reach 5.129:1, and the action orange as outline-button text reaches at least 4.622:1 on every light surface in the stylesheet. The focus ring uses `#2393cf` (3.417:1 on white, 3.425:1 on the purple header) instead of `#007ab7` (2.490:1 on purple). The original orange is retained for the decorative form-error accent border. `tests/test_fedex_contrast.py` recomputes these ratios from the stylesheet.

Read-only routes never write. Browsing, searching and tracking leave the seeded database byte-identical, so reset and read-only state grading stay exact.

## Seed generation

The seed is a pure function of tracked source. `seed_data.py` builds `instance_seed/fedex.db` from the models in `app.py` and the guide text in `support_content.py`, in a single transaction, and then validates the result before keeping it: row counts, referential integrity under `PRAGMA foreign_keys`, the `seed_metadata` schema marker `fedex-source-v2`, and the absence of any unsupported relation. A validation failure aborts the build instead of producing a partial database.

Two runs produce byte-identical files within one SQLite runtime. Benchmark password hashes use a fixed per-account salt for that reproducibility; accounts registered at runtime still get a random salt. Different SQLite versions can encode equivalent rows differently, so the image build (SQLite 3.40.1) and a workstation build (3.45.1) hash differently while every row is identical and every derived grading target matches; reset comparisons use the seed rebuilt inside the same container runtime. The generator pins its own database URI, so an ambient `FEDEX_DATABASE_URI` cannot redirect the build.

Because the seed is generated, the Hugging Face archive for this site is media-only. The Docker build runs the generator after validating the media inventory, so the image contains no opaque seed binary and no answer key that is not derivable from tracked source.

There is no in-place seed maintenance command. To change seeded content, edit `support_content.py` or `seed_data.py` and regenerate; a seed that was patched after generation would no longer match a cold build.

## Tasks and grading

The accepted set contains 18 tasks with one rubric and one verifier per task. Tasks 2 and 11 require detail-specific information and cross-page reading, rather than generic demo boilerplate. Task 10 explicitly names the locations navigation already required by its rubric. Task 12 states the delivery mode it grades.

No answer key is stored anywhere in this site. `verify/ground_truth.py` derives every graded target from the initial database supplied to the verifier, and fails closed when a target is ambiguous rather than guessing. `tasks.jsonl` carries task inputs, which may name an account, a tracking number or a location, but never a graded result.

Ground truth lives in exactly two places: the seed generator, which writes the answers into the database a run reads, and the verifiers, which re-derive them from the initial database they are given. The answer-isolation tests in `tests/test_fedex_assets.py` enforce that boundary. They derive the graded identifiers and the distinctive graded values from the seed at run time, then fail if either appears in the task manifest, in help copy, or in any other tracked file under this site outside `verify/` and `seed_data.py`. Tests, documentation and templates must derive those values rather than restate them.

## Regression check

After fetching the paired assets, from the repository root:

```sh
python -m pytest sites/fedex/tests -q
node --check sites/fedex/static/js/main.js
bash scripts/check_assets.sh
```

The suite covers the task contract, ground-truth derivation and uniqueness, verifier rejection of degraded evidence, local route behavior, media and inventory hashes, seed reproducibility and preservation, session and CSRF protection, cross-account authorization, input bounds without server errors, pickup capacity, foreign-key enforcement, error pages, WCAG contrast for the real button and focus states, and the offline asset surface.

These are deterministic regression tests. They are not recorded agent trajectories, and they do not replace browser execution, visual comparison, full-environment integration or independent review.
