# FedEx

An offline FedEx mirror contributed in [WebHarbor #50](https://github.com/aiming-lab/WebHarbor/pull/50) and revised in [WebHarbor #82](https://github.com/aiming-lab/WebHarbor/pull/82), with package tracking, rate estimates, a shipping flow, pickup scheduling, a location directory, local support articles, accounts, shipment history, invoices and claims. FedEx uses port **40024** in the current 25-site registry.

## Data and assets

- The environment is synthetic business data, not live FedEx facts. `seed_data.py` generates `instance_seed/fedex.db` from tracked source: 4 benchmark accounts, 15 staffed locations with 45 pickup slots, 5 service levels, 60 shipments with 60 invoices, 72 tracking records with 360 timeline events, 12 claims, 8 pickup requests, 3 seeded search log entries and 18 support articles across 13 tables.
- The seed is byte-reproducible within one SQLite runtime. Two cold builds from tracked source produce identical files, because benchmark password hashes use a fixed per-account salt while accounts registered at runtime still get a random salt. Different SQLite versions can encode equivalent rows differently, so the file hash depends on the runtime that built it: the image builds SQLite 3.40.1 while a workstation may build 3.45.1, and the two hashes differ although every row is identical. Reset comparisons therefore use the seed rebuilt inside the same container runtime, and the grading targets are derived from whichever database a run is given rather than from a recorded hash. The generator writes in a single transaction, then validates row counts, referential integrity under enforced foreign keys, the `seed_metadata` marker `fedex-source-v2` and the absence of unsupported relations; a validation failure aborts the build instead of leaving a partial database. The generator also pins its own database URI, so an ambient `FEDEX_DATABASE_URI` cannot redirect the build.
- `.build-generated-seed` records that the database is built rather than downloaded, so the Hugging Face archive for this site is media-only. The Docker build runs the generator after validating the media inventory.
- `.requires-external-cache` records that the media is a build dependency. `asset_inventory.json` binds all 18 media files, 1,000,422 bytes, to a direct `https` source URL, a byte length and a SHA-256 value; `docs/homepage-assets.json` records the same data with the source page and capture method. Every entry, including the logo, has a direct URL, and each was re-downloaded and compared by hash against the cached bytes. `scripts/check_asset_inventory.py` verifies paths, hashes, URL schemes and file-format headers from `scripts/check_assets.sh` and from the Docker build, so a missing, altered or unaccounted media file fails the build. Local files are never downloaded by the running site.
- Third-party material, including the two FedEx Sans web fonts and their embedded copyright and licence records, is dispositioned in `NOTICE.md`, together with the non-affiliation statement and the removal procedure.
- `support_content.py` is the canonical text for the 18 local guides. The articles explain this interface; they quote no dataset row and restate no graded answer, so a run cannot answer a task by reading help copy instead of visiting the page the task requires.

## Grading

The accepted set contains **18 tasks**, `FedEx--0` through `FedEx--17`, with one rubric and one verifier per task under `verify/`.

No answer key is stored in this site. `verify/ground_truth.py` derives every graded target from the initial database supplied to the verifier, and fails closed when a target is ambiguous rather than guessing. `verify/verify_lib.py` binds evidence to a task id and to a trusted local origin, requires screenshots that decode as images of a minimum size, requires the tables a read-only task names to be unchanged, matches an answer against negation-aware relations instead of substring presence, and reports a structured failure rather than a traceback on malformed input. It accepts the trajectory schema `agent_demo/agent.py` actually writes, including the `url_after` convention the other sites use.

Ground truth lives in exactly two places: the seed generator, which writes the answers into the database a run reads, and the verifiers, which re-derive them from the database they are given. The answer-isolation tests derive the graded identifiers and the distinctive graded values from the seed at run time and fail if either appears in the task manifest, in help copy, or in any other tracked file outside `verify/` and `seed_data.py`.

## Local use

From the repository root, install the site's requirements and fetch its pinned assets:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r sites/fedex/requirements.txt huggingface_hub pytest pillow
./scripts/fetch_assets.sh fedex
.venv/bin/python sites/fedex/seed_data.py
mkdir -p sites/fedex/instance
cp sites/fedex/instance_seed/fedex.db sites/fedex/instance/fedex.db
PORT=40024 .venv/bin/python sites/fedex/app.py
```

`FEDEX_DATABASE_URI` overrides the database location and `FEDEX_SECRET_KEY` pins the session signing key. Without `FEDEX_SECRET_KEY` the key is generated per process, so no session cookie can be forged from a value in this repository. `WEBSYN_SKIP_BOOTSTRAP=1` is reserved for isolated tests. The full environment should be started with the repository's Docker and control-plane workflow so that reset restores the complete seed.

Benchmark logins use password `TestPass123!`: `alice.j@test.com`, `bob.c@test.com`, `carol.d@test.com`, and `david.k@test.com`. Task dates are fixed, so tracking timelines, estimates and due dates remain valid independently of wall-clock time.

```bash
.venv/bin/python -m pytest sites/fedex/tests -q
node --check sites/fedex/static/js/main.js
bash scripts/check_assets.sh
```

Tests cover ground-truth derivation and uniqueness for all 18 tasks, the grading contract against the real `verify_N.py` entry points, verifier rejection of contradictory, answer-only, foreign, forged, truncated and wrong-task evidence, answer isolation, local route behavior, media and inventory hashes, seed reproducibility and preservation, session and CSRF protection, cross-account authorization, input bounds without server errors, pickup capacity, foreign-key enforcement, error pages, and the offline asset surface. They are deterministic regression tests, not recorded agent trajectories, and they do not replace browser execution, visual comparison or full-environment integration.

## Interface scope

The homepage hero, official typography, navigation, tracking timeline, rate cards, shipping stepper, location cards and directory, support index and article layout, and account history follow the public site. Desktop and mobile use their respective original hero images, and the browser synthesizes the bold weight from the two shipped font files.

Read-only routes never write. Browsing, searching and tracking leave the seeded database byte-identical, so reset and read-only state grading stay exact. The 3 seeded `search_logs` rows are written by the generator only; no route appends to that table at runtime.

Eleven routes change state, and all of them require a POST carrying a CSRF token, with no exemptions: sign-in, sign-out, registration, profile edits, the three shipping steps, pickup scheduling, rate estimation, tracking lookup and shipment removal. Sign-out is not reachable with GET or HEAD. Invoices and claims are read-only views, so this mirror implements no payment, dispute or claim-filing action; those entry points open an offline notice instead.

Two brand pairings were adjusted for contrast, and `tests/test_fedex_contrast.py` recomputes the ratios from the stylesheet so they cannot regress. White on the original FedEx orange measured 2.936:1 at 16px/700, which is below the large-text threshold and so required 4.5:1; action surfaces and labels now use `--fedex-orange-action` (`#ba4b00`). White labels reach 5.129:1, and the same orange used for outline-button text reaches at least 4.622:1 on every light surface in the stylesheet. The focus outline `#007ab7` measured 2.490:1 against the purple header, below the 3:1 non-text threshold; the focus ring is now `--focus-ring` (`#2393cf`), which reaches 3.417:1 on white and 3.425:1 on purple, so it is visible in both contexts. The original `#f60` is kept only for the decorative accent border on the form-error summary, where no text or component-identification requirement applies, and a test pins that restriction.

The collapsible navigation and the offline-availability notices are `<details>` and `<dialog>` elements driven by `static/js/main.js`. Below 900px the primary navigation is behind the menu button, and the offline notices open as a modal, so both need scripting; this matches the pattern the merged Compass mirror uses. With scripting enabled every route, control and notice is reachable at 1440, 768, 390 and 320px, and no page overflows horizontally at any of those widths. Without scripting the desktop-width navigation and the `<details>` menus still work, but the sub-900px menu button and the modal notices do not respond.

Marketing, printing, sweepstakes, refunds, corporate links, social links and app downloads preserve their homepage entry points but open an offline-availability notice. Those live workflows are not implemented; these are functional scope limits, not measures to prevent answer leakage. Tracking, rates, shipping and pickup scheduling do not contact FedEx, purchase shipping or create real carrier bookings.

Identifier allocation is derived from the records that already exist rather than from a counter in the session, so creating, removing and recreating a shipment or a pickup produces coherent codes and cannot collide with a seeded row or fail after a removal. A new shipment's status, timeline and estimate are derived from the service the run selected.
