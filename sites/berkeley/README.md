# UC Berkeley mirror

Offline Flask mirror of `https://www.berkeley.edu/`. In the 30-site registry it is site index 29 and runs on container port `40029`. Every college, department, programme, faculty member, research centre, article, event and account is deterministic synthetic benchmark data; only the page chrome mirrors upstream.

## Runtime

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python Flask==3.1.0 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 \
  Flask-WTF==1.2.2 Flask-Bcrypt==1.0.1 email-validator==2.2.0   # the shared pins; no site-specific deps
./scripts/fetch_assets.sh berkeley                                              # static/images/ from the HF tarball
cd sites/berkeley && PYTHONHASHSEED=0 ../../.venv/bin/python seed_data.py      # writes instance_seed/berkeley.db
PORT=40029 ../../.venv/bin/python app.py
```

`.build-generated-seed` marks the **seed** as build-generated: the Docker build regenerates `instance_seed/berkeley.db` from the tracked `seed_data.py` (`cd /opt/WebSyn/berkeley && rm -rf instance instance_seed && PYTHONHASHSEED=0 python seed_data.py && rm -rf instance`) and `scripts/fetch_assets.sh` drops any `instance_seed/` it finds in the archive. The seed is byte-reproducible — md5 `3001bcf4bcec169f4192c08609160ab6`, identical under `PYTHONHASHSEED=0` and `=1` — because the four benchmark password hashes are precomputed bcrypt strings, every `created_at` is the frozen clock, and `User.email`/`User.username` carry `unique=True` without `index=True` (SQLAlchemy emits named indexes in set-iteration order, which moved SQLite root pages between runs).

The **imagery** is the opposite: `.requires-images` marks `static/images/` as archive-shipped, so `scripts/check_assets.sh` treats an empty `static/images/` as a hard failure until `fetch_assets.sh` has run. The Docker build gates the bundle with `check_generated_assets.py` before generating the seed.

## Frozen benchmark clock

`app.py` defines `BENCHMARK_NOW = datetime(2026, 5, 12)` and uses it everywhere a date is compared or stamped (the `/events` upcoming/past/today filters, the homepage "Upcoming events" block, and the `created_at` / `published_date` column defaults via `utcnow()`). No request or seed path calls `datetime.utcnow()`, so the rendered site is identical on any run date; against the seeded calendar `/events` admits 52 of 64 rows, 15 of them Lecture. Reseeding with a different `now` means re-pinning the verifier contract in `verify/verify_lib.py` (schema hash, counts, catalog fingerprint).

## Imagery — synthetic, and what that means

164 generated files, all declared in `generated_asset_inventory.json` and gated by
`check_generated_assets.py`:

| kind | files | pixels | how |
|---|---|---|---|
| `campus` | 8 | 1024×768 WebP | section heroes and banners |
| `college` | 14 | 1024×768 WebP | one per college; odd ids a building exterior, even ids an interior |
| `research` | 25 | 1024×768 WebP | one per research centre |
| `news` | 21 | 1024×768 WebP | 7 categories × 3 variants, variant = `article.id % 3 + 1` |
| `event` | 14 | 1024×768 WebP | 7 categories × 2 variants, variant = `event.id % 2 + 1` |
| `faculty` | 82 | 256×256 PNG | deterministic Pillow initials avatars |

**Provenance.** The 82 scene photographs were generated on 2026-09-14 with
**fal.ai FLUX.1 [schnell]** (4 inference steps, one fixed seed per slot derived
from its slug) and converted to WebP q82. The 82 faculty avatars are **not**
model-generated: `scripts/gen_avatars.py` draws each one with Pillow 11.0.0
from the faculty row's initials and id, so the bytes are reproducible with no
network and no RNG.

**Prompt policy.** Every scene prompt is one subject clause plus a fixed style
suffix plus a fixed negative list — `no text, no lettering, no logos, no
watermarks, no faces, no portraits, no recognizable landmarks or signage,
photographic, natural light, no posters, no framed pictures, no screens with
visible content, unlabeled containers` — with `bright natural daylight` and
`plain blank walls and panels` in the style suffix. Subjects come from the seed
row the page already renders (name, description, and for centres the focus
areas); the exact prompt for each file is recorded in the inventory. Slots are
occupancy-classified: **labs and research interiors are prompted empty**;
campus, event and college-exterior slots permit only figures seen from behind or
at a distance.

**No real people, no real places.** No image depicts a real person, a
recognisable face, or a real landmark: the campus scenes are generic
institutional architecture, specifically *not* the Campanile, Sather Gate, the
Golden Gate or any other identifiable Berkeley or Bay Area feature. The faculty
avatars are monogram discs, never likenesses. As with the seeded rows, the whole
site is labelled synthetic on every page.

**Verification, and its limits.** `check_generated_assets.py` enforces exact
coverage (no missing, stale or undeclared file), per-file SHA-256, a full decode
at the planned dimensions, a letterbox test (three of the first 82 frames came
back with black bars), and — where `pytesseract` is present — an OCR pass.

Neither pass is a guarantee, and the limits are measured rather than assumed.
The OCR pass has a positive control that proves it **can** fire on clean
rendered text, but it does not reliably detect legible text at all: it returned
zero tokens for the word `STCK` rendered in large red capitals across a window
in `colleges/chemistry.webp`, and missed a warning placard in
`research/bair.webp` entirely. The face pass is a *frontal-face* cascade, not a
person detector: the OpenCV defaults returned 15 false positives across five
clean pilot scenes (tree foliage, mown grass) and were replaced with settings
that score zero there and detect a generated face control — which is exactly
why it also misses the small, profile faces the no-faces rule cares about, and
why the `event` family was moved to unoccupied prompts. Tesseract also flagged
six clean scenes on three-character junk (`aif`, `hea`, `saks`) until the
confidence floor was raised.

`scripts/IMAGE_PLAN.md` §9 records every measurement and every miss.
`tests/test_generated_assets.py` exercises both detectors against positive
controls, so a green run shows the detectors can fire — not that the bundle is
text- and face-free. What actually bounds text and faces is the prompt plus the
contact sheet reviewed by eye, which is what found `STCK`, the seated person,
the crowds with faces to camera, the framed portrait and the black bars.

**Non-affiliation.** This is an unofficial offline benchmark mirror. The names,
descriptions and numbers are synthetic benchmark data, and the imagery is
machine-generated; nothing here is provided by, endorsed by, or affiliated with
the University of California, Berkeley or the Regents of the University of
California.

**Regenerating.** `scripts/gen_images.py` (scenes; needs `FAL_KEY`) and
`scripts/gen_avatars.py` (avatars; offline). A slot whose bytes, prompt and
seed already match an accepted inventory row is skipped, so a partial re-run
costs only the missing calls.

## Seeded rows

| Model | Rows | Model | Rows |
|---|---|---|---|
| colleges | 14 | departments | 30 |
| programmes | 83 (25 PhD / 21 BA / 16 BS / 16 MS / MBA, JD, MEng, MD, MPH ×1; 17 GRE-required, 1 online) | faculty | 82 (19 EECS) |
| research centres | 25 | news articles | 121 (7 Athletics) |
| events | 64 (19 Lecture / 14 Career / …) | users | 4 |

Benchmark accounts: `alice`, `bob`, `carol`, `dave` `@berkeley.edu`, password `test1234` (public by design; the hashes are hardcoded in `seed_data.py`). The `bookmarks` table starts empty, so the two stateful tasks bind their insert/delete ordering to the row ids the app assigns.

## Routes

`/`, `/news` (search + category + pagination), `/news/<slug>`, `/academics`, `/programs` (search, college and degree filters, pagination), `/programs/<slug>`, `/events` (category + upcoming/past/today), `/events/<id>`, `/research`, `/research/<slug>`, `/departments`, `/departments/<slug>`, `/admissions`, `/about`, `/search` (programmes / news / events / faculty / centres), `/faculty` (name, interest and department filters), `/faculty/<slug>`, `/login`, `/register`, `/logout` (POST-only, CSRF-protected: a prefetching GET gets 405), `/account` (bookmarks), `/bookmark/add` (POST), `/bookmark/remove` (POST), `/_health`.

Article detail, programme detail, event detail, faculty profiles and centre pages are pure reads: no GET path writes the database, so a read-only benchmark task's after-state always equals its initial snapshot. `sites/berkeley/tests/` holds the runnable checks: registry/seed integration, the answer-leak sweep (`test_answer_leaks.py`), the app-robustness suite (`test_app_robustness.py`) and the generated-asset gate (`test_generated_assets.py`, which verifies inventory count and hashes, that no undeclared file sits under `static/images/`, that every `<img>` the templates render resolves to a file on disk, and that the OCR and face passes hold with their positive controls — skipping if the bundle has not been fetched).

Every `<img>` carries an explicit `width`/`height` and sits in an aspect-ratio or fixed-height box so nothing shifts as photos decode, and its `alt` is built from the same seed fields the page already renders — never a title, director, founding year or focus area, which are the graded answers on the detail pages.

## Grading contract

`sites/berkeley/verify/` holds the deterministic verifiers (one per `tasks.jsonl` row), the shared `verify_lib.py`/`ground_truth.py`, and `TASK_REVIEW.md` with the per-row ACCEPT/DROP/ADDED record. See `verify/README.md` for the snapshot contract and how to run them.
