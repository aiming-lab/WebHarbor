# UC Berkeley mirror — imagery plan (normative)

Status: Phase 1 discovery output, revised after the pilot review.
Owner: `scripts/gen_images.py` (scenes) + `scripts/gen_avatars.py` (faculty).

This file is the specification, not a description: `gen_images.py` parses the
`gen_images:prompt-spec` JSON block in §3 at run time, so the slot table, the
style suffixes, the negative list and every subject template below are the
single source of truth for what gets generated and what lands in
`generated_asset_inventory.json`.

Revision 2 (post-pilot) changed: the negative list (§3.1), two occupancy-aware
style suffixes replacing one (§3.2), a poster/screen-safe rewrite of every
motif and theme table, exterior/interior alternation for the 14 colleges
(§3.3), and a mandatory automated QA pass with per-slot seed retry (§9).

## 0. Why this site had none, and what changes

`sites/berkeley` ships **no images at all** today: `static/` holds only
`static/css/.gitkeep` and `static/js/.gitkeep`, `base.html` carries one inline
stylesheet, the logo is a CSS circle (`<div class="logo-mark">C</div>`,
`templates/base.html:324`), and the card imagery is a flat `background:` colour
plus a text label (`.card-img`, `templates/base.html:134`). `README.md`
§Imagery states the omission is "by design".

That is a real fidelity gap for a mirror of `berkeley.edu`, whose every section
page leads with a photograph. This plan closes it without touching a single
task-visible fact: every image is synthetic, generated from the same seed rows
the templates already render, and carries no text.

Deviations from the brief's slot model are listed in §6 with their reasons.

## 1. Slot model

Counts follow the brief: hero/campus 8, colleges 14, research centres 25,
news 7 categories × 3 variants, events 7 categories × 2 variants, faculty
82 deterministic avatars. 82 scene files + 82 avatars = **164 files**.

| # | kind | root | files | one per | slug | driven by |
|---|---|---|---|---|---|---|
| A | `campus` | `static/images/campus/` | 8 | section hero | fixed table §3.4 | fixed scene table |
| B | `college` | `static/images/colleges/` | 14 | `colleges.slug` | `colleges.slug` | `colleges.name`, `.description`, id parity |
| C | `research` | `static/images/research/` | 25 | `research_centers.slug` | `research_centers.slug` | `.name`, `.description`, `.focus_areas` |
| D | `news` | `static/images/news/` | 21 | 7 categories × 3 variants | `<category-slug>-<v>` | category theme (no article fields) |
| E | `events` | `static/images/events/` | 14 | 7 categories × 2 variants | `<category-slug>-<v>` | category theme (no event fields) |
| F | `faculty` | `static/images/faculty/` | 82 | `faculty.slug` | `faculty.slug.png` | `faculty.name` (initials only) |

### Deterministic variant assignment

Nothing about a slot may depend on render order, so multi-variant families bind
the variant to the **primary key**, not to a loop index:

```python
news_variant(article) = (article.id % 3) + 1      # 1..3
event_variant(event)  = (event.id % 2) + 1        # 1..2
```

`news` category → family: the app exposes exactly seven categories
(`app.py:384`). The seed holds an eighth value, `Academics`, on **one** row of
121; that row falls back to `campus-life` and is the only documented family
mismatch (§6.2).

`events` categories are exactly the seven seeded values, so no fallback is
needed. The category → slug map is `lower()`, spaces → `-`.

## 2. Template slots — every `<img>` this plan adds

Read-only survey of `sites/berkeley/templates/*.html` at `8e5bb7f`. Line
numbers are as of that commit. "alt" is the template expression, never a
literal, so the alt text is always the same seed row the page already renders.

### 2.1 `index.html` — home page

| line | block | slot | img |
|---|---|---|---|
| 7 | hero `linear-gradient(135deg, #003262 60%, #2E6C8B 100%)` overlay div, inside `<section style="background: var(--blue)…">` | A `campus-quad` | full-bleed background layer under the gradient, `alt=""` (decorative; the hero already has an `h1`) |
| 60–65 | lead-story `<div style="background: var(--blue); min-height: 240px; …">` holding `<div style="font-size: 48px;">🌐</div>` | D news family of `featured_news[0]` | `<img>` replaces the globe glyph |
| 82–84 | `<div class="card-img" style="background: …; height: 120px;"><span class="card-img-label">{{ article.category }}</span></div>` | D for each `featured_news[1:]` | `<img>` inside `.card-img`; the label span stays as the overlay caption |
| 108–111 | event date block `<div style="background: var(--blue); padding: 20px; …">` | E family of each `upcoming_events` | date block stays; image added above it inside `.card` |
| 135–140 | research card `<div class="card"><div class="card-body">` (no image block today) | C `recent_research` | new `.card-img` inserted before `.card-body` |

### 2.2 `news.html` — news listing

| line | block | slot | img |
|---|---|---|---|
| 53–56 | `<div class="card-img" style="background: {% if article.category == 'Research' %}#003262 … %}"><span class="card-img-label">{{ article.category }}</span>` | D | `<img>` inside `.card-img`; the per-category background colour stays as the fallback layer, and the label span stays |

### 2.3 `news_article.html` — news detail

| line | block | slot | img |
|---|---|---|---|
| 38–43 | "Article image placeholder" `<div style="background: var(--blue); height: 280px; …">` with the 🎥 glyph and the literal `Berkeley News` | D, the article's own variant | `<img>` replaces the glyph block |

### 2.4 `events.html` — events listing

| line | block | slot | img |
|---|---|---|---|
| 53–59 | `<div style="background: {% if event.category == 'Lecture' %}#003262 … %} …">` date block + `<span class="badge …">{{ event.category }}</span>` | E | `<img>` inserted above the date block; date block and badge untouched |

### 2.5 `event_detail.html` — event detail

| line | block | slot | img |
|---|---|---|---|
| 20–25 | `.container.py-4 > .sidebar-layout > div`, opening with `<h2 class="section-heading">About This Event</h2>` | E, the event's own variant | 280 px banner between the page header and "About This Event" |

### 2.6 `faculty.html` — faculty directory

| line | block | slot | img |
|---|---|---|---|
| 39–43 | `<div style="background: {% if member.is_emeritus %}#55595E{% else %}var(--blue){% endif %}; height: 80px; …"><div style="width: 60px; height: 60px; background: var(--gold); border-radius: 50%;">…{{ member.name[0] }}</div></div>` | F avatar | `<img>` replaces the 60 px initials disc; the 80 px band and the emeritus grey stay |

### 2.7 `faculty_profile.html` — faculty detail

| line | block | slot | img |
|---|---|---|---|
| 16–18 | `<div style="width: 80px; height: 80px; background: var(--gold); border-radius: 50%; …">{{ member.name[0] }}</div>` inside the page-header flex row | F avatar | `<img>` replaces the disc, same 80 px box |

### 2.8 `academics.html` — schools & colleges

| line | block | slot | img |
|---|---|---|---|
| 34–35 | `<div class="card"><div class="card-body">` (no image block) | B `college.slug` | new `.card-img` before `.card-body` |

### 2.9 `departments.html` / `department_detail.html`

| line | block | slot | img |
|---|---|---|---|
| `departments.html:21–22` | `<div class="card"><div class="card-body">` per department | B of `dept.college` (§6.1) | new `.card-img` before `.card-body` |
| `department_detail.html:13–18` | `.page-header` with `<h1>{{ dept.name }}</h1>` | B of `dept.college` | banner behind the page header, blue scrim, `alt=""` |

### 2.10 `research.html` / `research_center.html`

| line | block | slot | img |
|---|---|---|---|
| `research.html:32–33` | `<div class="card"><div class="card-body">` per centre | C `center.slug` | new `.card-img` before `.card-body` |
| `research.html:14` | overview `split-3-2` panel | A `campus-labs` | 4:3 image above the "The World's Top Public Research University" copy |
| `research_center.html:13–18` | `.page-header` | C `center.slug` | banner behind the page header, blue scrim |

### 2.11 `about.html`, `admissions.html`, remaining section headers

| file | line | block | slot |
|---|---|---|---|
| `about.html` | 12–17 | mission block, `max-width: 800px; text-align: center` | A `campus-library` full-width band above the block |
| `about.html` | 37–55 | History/Location `split-3-2` | A `campus-quad` in the History column |
| `admissions.html` | 12–17 | `#undergraduate` section opening | A `campus-admissions` banner |
| `academics.html` | 5–10 | `.page-header` | A `campus-lecture-hall` banner behind the header, blue scrim |
| `news.html` | 5–10 | `.page-header` | A `campus-newsroom` banner |
| `events.html` | 5–10 | `.page-header` | A `campus-events-green` banner |
| `faculty.html` | 5–10 | `.page-header` | A `campus-faculty-office` banner |

Not imaged, deliberately: `/programs`, `/programs/<slug>`, `/search`, `/login`,
`/register`, `/account`, `404.html`, `500.html`, `base.html` (§6.3).

## 3. Prompt construction

For every scene slot:

```
prompt = "<subject clause>, <style suffix for this slot's occupancy>, <NEGATIVE>"
```

### 3.1 Negative list (fixed, byte-identical for every slot)

```
no text, no lettering, no logos, no watermarks, no faces, no portraits,
no recognizable landmarks or signage, photographic, natural light,
no posters, no framed pictures, no screens with visible content,
unlabeled containers
```

`fal-ai/flux/schnell` exposes no separate negative-prompt field, so `NEGATIVE`
is folded into the prompt text as a trailing constraint clause rather than
dropped.

### 3.2 Occupancy and the two style suffixes

The pilot produced two defects this section exists to prevent: a seated person
in a research interior, and a framed portrait poster on a lab wall. Occupancy
is now a **property of the slot**, not a global setting, and anything that is
not explicitly an exterior gets the empty variant.

**Events are `empty` too.** §9.2's by-eye review found the `event` prompts, which
describe *gatherings*, pulling crowds in facing the camera in four of the six
slots sampled — against zero of the five sampled campus and college-exterior
slots, which hold the "backs turned" constraint reliably. An unoccupied hall,
stadium or courtyard still reads correctly as an event venue, so the event
family moved to `style_suffix_empty` via `"event_occupancy"`. Where people
remain permitted they are an affordance the model can decline, never a
requirement.

`style_suffix_people` — used by campus scenes marked `people` and `college`
slots on an **exterior** subject:

```
editorial photograph for a university website, bright natural daylight,
natural but vivid colours, wide establishing shot, shallow depth of field,
a few students seen from behind or at a distance, no faces visible,
plain blank walls and panels, no placards, no labels, no notices,
no banners, no lettering of any kind anywhere in the scene,
4:3 landscape composition
```

`style_suffix_empty` — used by every `research`, `news` and `event` slot,
`college` slots on an **interior** subject, and campus scenes marked `empty`:

```
editorial photograph for a university website, bright natural daylight,
natural but vivid colours, wide establishing shot, shallow depth of field,
completely unoccupied space with no people present and no human figures
anywhere in frame, plain blank walls and panels, no placards, no labels,
no notices, no banners, no lettering of any kind anywhere in the scene,
4:3 landscape composition
```

People are never *required* by the prompt — `people` slots merely permit small
distant figures seen from behind. §9's face detector is the enforcement; the
suffix is the steering.

### 3.3 `gen_images:prompt-spec`

```json
{
  "model": "fal-ai/flux/schnell",
  "num_inference_steps": 4,
  "image_size": "landscape_4_3",
  "output_format": "jpeg",
  "style_suffix_people": "editorial photograph for a university website, bright natural daylight, natural but vivid colours, wide establishing shot, shallow depth of field, at most two or three people far away in the middle distance walking away from the camera, backs turned, faces completely hidden, no crowds, no visible faces, plain blank walls and panels, no placards, no labels, no notices, no banners, no lettering of any kind anywhere in the scene, 4:3 landscape composition",
  "style_suffix_empty": "editorial photograph for a university website, bright natural daylight, natural but vivid colours, wide establishing shot, shallow depth of field, completely unoccupied space with no people present and no human figures anywhere in frame, plain blank walls and panels, no placards, no labels, no notices, no banners, no lettering of any kind anywhere in the scene, 4:3 landscape composition",
  "negative": "no text, no lettering, no logos, no watermarks, no faces, no portraits, no recognizable landmarks or signage, photographic, natural light, no posters, no framed pictures, no screens with visible content, unlabeled containers",
  "campus": {
    "campus-quad": {"occupancy": "people", "subject": "a wide grassy quad framed by generic institutional university buildings and mature trees"},
    "campus-library": {"occupancy": "people", "subject": "a university library reading room with tall windows, long tables and green reading lamps"},
    "campus-labs": {"occupancy": "empty", "subject": "a modern research laboratory interior with fume hoods and analytical instruments"},
    "campus-lecture-hall": {"occupancy": "people", "subject": "a tiered lecture hall with wooden seats and a large bare chalkboard"},
    "campus-admissions": {"occupancy": "people", "subject": "a sunlit campus gateway path lined with trees leading toward generic institutional buildings"},
    "campus-newsroom": {"occupancy": "empty", "subject": "a university newsroom of completely bare desks with dark blank monitors, an entirely empty floor and completely bare walls, nothing pinned or taped to the walls, no whiteboards, no boxes, no crates, no packaging and no printed material anywhere in the scene"},
    "campus-events-green": {"occupancy": "people", "subject": "an open campus green with a small outdoor stage and rows of folding chairs"},
    "campus-faculty-office": {"occupancy": "empty", "subject": "a faculty office with bare shelves, a writing desk and a window onto trees, on completely bare walls with no wall art, no framed pictures, no posters and no books with visible spines"}
  },
  "college_exterior": "{name} at an unnamed American public research university: {description_160}, {exterior_motif} on a generic university campus",
  "college_interior": "{name} at an unnamed American public research university: {description_160}, {interior_motif} on a generic university campus",
  "research": "a research institute interior for the {name}: {description_160} Research focus: {focus_areas_3}. {lab_motif} at an unnamed American public research university",
  "news": "a {news_theme} for a campus news story about {category}, variant {variant}: {variant_motif}",
  "event": "a {event_theme} for a campus event in the {category} category, variant {variant}: {variant_motif}",
  "variant_motif": {
    "1": "a wide establishing view of the whole space",
    "2": "a closer view of the objects and materials in the space",
    "3": "an interior view from a raised corner of the space"
  },
  "event_occupancy": "empty",
  "news_theme": {
    "research": "research laboratory bench with glassware and stainless instruments",
    "campus-life": "campus plaza with benches and trees between buildings",
    "faculty": "faculty office with bare shelves, a writing desk and a window, on completely bare walls with no wall art, no framed pictures, no posters and no books with visible spines",
    "student": "student study area with long tables and reading lamps, on completely bare walls with no wall art, no framed pictures, no posters and no books with visible spines",
    "athletics": "outdoor running track and sports field at the edge of campus",
    "science": "an empty science building corridor with plain bare walls, a terrazzo floor and tall windows, nothing mounted on the walls",
    "arts": "art studio with easels and a small bare stage"
  },
  "event_theme": {
    "lecture": "lecture hall auditorium with rows of seats and a bare podium",
    "sports": "outdoor stadium field and running track",
    "arts": "performance hall stage with warm stage lighting and a bare backdrop",
    "career": "a deserted exhibition hall with long bare folding tables and no display material, no brochures, no leaflets, no stands, no people",
    "health": "health sciences seminar room with a long table",
    "social": "campus courtyard set with long tables for an outdoor gathering",
    "virtual": "video-conferencing studio with dark blank screens and a desk"
  },
  "exterior_motif": {
    "1": "limestone humanities quad with arcades and mature trees",
    "2": "modern brick and glass engineering building entrance",
    "3": "business school courtyard with clean modern paving",
    "4": "law school entrance with stone columns and wide steps",
    "5": "glass-fronted information school entrance",
    "6": "chemistry building façade with tall laboratory windows",
    "7": "education school entrance with a wide low staircase",
    "8": "public health building entrance with a planted forecourt",
    "9": "environmental sciences building beside a stand of trees",
    "10": "design school courtyard with concrete benches",
    "11": "policy school entrance with a stepped plaza",
    "12": "social welfare building entrance with a small garden",
    "13": "journalism school entrance with a glazed corner, seen from behind at a distance; any figure is walking away with its back to the camera and no face visible to the viewer",
    "14": "optometry clinic entrance with a covered walkway"
  },
  "interior_motif": {
    "1": "lecture hall with tiered wooden seats",
    "2": "engineering workshop with long benches and bare walls",
    "3": "business school atrium with a bare open staircase",
    "4": "a completely unoccupied law library reading room with long empty tables, empty shelves and no people at all, bare walls, no wall art, no framed pictures, no posters, no books with visible spines",
    "5": "information commons with rows of bare desks, no wall art, no framed pictures, no posters, no books with visible spines",
    "6": "a spotless empty chemistry laboratory with completely bare stainless steel benches, nothing on the benches, no glassware, no bottles, no containers, no trays and no boxes to carry a label, plain unmarked windows and plain bare walls, no whiteboards, no chalkboards, no notice boards and nothing mounted on the walls",
    "7": "education seminar room with a long table and empty chairs, no wall art, no framed pictures, no posters",
    "8": "public health laboratory with bare benches",
    "9": "field station room with bare storage bins and a workbench",
    "10": "design studio with drafting tables and bare partitions, no wall art, no framed pictures, no posters, no books with visible spines",
    "11": "policy seminar room with a large bare table",
    "12": "community services office with bare desks, no wall art, no framed pictures, no posters, no books with visible spines",
    "13": "broadcast studio with dark blank monitors and empty chairs, no wall art, no framed pictures, no posters",
    "14": "optometry clinic room with a bare examination chair"
  },
  "lab_motif": {
    "1": "bright open-plan robotics and computing laboratory with long workstations, every monitor switched off and dark, and a single articulated robot arm",
    "2": "open data-science collaboration space with long shared desks and bare walls, no wall art, no framed pictures, no posters, no books with visible spines",
    "3": "mathematics institute seminar room with a large bare chalkboard and rows of empty chairs",
    "4": "plant-growth chamber with rows of seedlings under grow lights",
    "5": "sensor and robotics bay with benches of bare metal instruments",
    "6": "green chemistry bench with glassware and stainless steel fume hoods",
    "7": "building-performance test chamber with a bare concrete wall and instrumented panels",
    "8": "seismograph vault with a concrete pier and cable runs",
    "9": "mathematics institute courtyard with a bare stone wall, planters and benches",
    "10": "urban planning studio with long drafting tables and bare walls, no wall art, no framed pictures, no posters, no books with visible spines",
    "11": "demography research office with rows of empty desks and bare partitions, no wall art, no framed pictures, no posters, no books with visible spines",
    "12": "labour studies reading room with long tables and bare walls, no wall art, no framed pictures, no posters, no books with visible spines",
    "13": "nanoscience clean room with stainless steel equipment and soft ambient light",
    "14": "field-research staging room with shelving of bare plastic crates and a workbench, no wall art, no framed pictures, no posters",
    "15": "biotechnology wet laboratory with stainless benches and glassware",
    "16": "design and fabrication shop with bare plywood benches and hand tools, no wall art, no framed pictures, no posters",
    "17": "new media studio with open floor space, bare partitions and soft light",
    "18": "health policy seminar room with a long table and rows of empty chairs",
    "19": "resilience operations room with a large bare table and empty chairs",
    "20": "international programmes office with rows of empty desks and bare walls, no wall art, no framed pictures, no posters, no books with visible spines",
    "21": "area studies reading room with long tables, bare walls and tall windows, no wall art, no framed pictures, no posters, no books with visible spines",
    "22": "policy analysis workspace with bare desks and tall windows, no wall art, no framed pictures, no posters, no books with visible spines",
    "23": "decentralized-systems laboratory with rows of dark blank screens and bare desks",
    "24": "EEG recording room with a bare reclining chair and instrument trolley",
    "25": "clinical research suite with a bare examination couch and soft natural light"
  }
}
```

`{description_160}` is `" ".join(description.split())` truncated at a word
boundary to ≤160 characters with the trailing punctuation stripped, so the
prompt is built from the seed row and is stable across runs.

All four motif tables are keyed by primary key (`colleges.id`,
`research_centers.id`), never by list position.

**College alternation:** `exterior_motif` when `colleges.id` is odd,
`interior_motif` when even — 7 of each, so the `/academics` card grid does not
read as fourteen rooms. Exterior slots take `style_suffix_people`; interior
slots take `style_suffix_empty` (several interiors are laboratories).

### 3.4 Seed

```
def seed_for(slug: str, attempt: int) -> int:
    return int.from_bytes(sha256(f"{slug}#{attempt}".encode()).digest()[:4], "big")
```

Fixed per (slot, attempt), derived from the slug, independent of run time,
ordering and `PYTHONHASHSEED`. Attempt 0 is the first generation; a §9 QA
failure re-runs the slot at attempt 1 then 2. The attempt that produced the
shipped file is recorded in the inventory as `seed`, so a re-run reproduces the
same bytes and the skip check stays exact.

### 3.5 Avatars — no model, no prompt, no network

Faculty avatars are **not** model-generated. `gen_avatars.py` draws them with
Pillow, following `sites/webmd_doctor/seed_data.py:1600-1631`:

* 256×256 RGB, `(241, 246, 250)` ground, filled circle in a palette colour
  chosen by `faculty.id % len(PALETTE)`, initials (`first[:1] + last[:1]`,
  upper) centred in white, `ImageFont.load_default(size=…)`;
* `save(..., format="PNG", optimize=False, compress_level=9, pnginfo=None)` —
  no `tIME`/`tEXt`/`zTXt`, so the bytes depend only on the pixels;
* the divider glyph the upstream site uses is **omitted**: the faculty rows
  name real people, and drawing an image that reads as their likeness is out of
  scope.

Every avatar is byte-reproducible: pinned `Pillow==11.0.0` (the repo `.venv`
and the Dockerfile agree), and no clock, RNG or set iteration reaches the draw
loop.

## 4. Output format

| kind | pixels | format | encoder | path |
|---|---|---|---|---|
| all scenes | 1024×768 | WebP | `quality=82`, `method=6` | `static/images/<kind>/<slug>.webp` |
| faculty | 256×256 | PNG | `optimize=False, compress_level=9, pnginfo=None` | `static/images/faculty/<slug>.png` |

`fal-ai/flux/schnell` returns 1024×768 for `landscape_4_3`; the generator still
asserts the decoded size and re-encodes through Pillow, so a provider-side size
change fails loudly instead of shipping an off-plan image.

WebP: `image.save(path, format="WEBP", quality=82, method=6)`. `method=6` is
the slow/deterministic search; `exif`/`icc_profile` are dropped so no generator
metadata reaches the file.

## 5. Inventory + gates

### 5.1 `generated_asset_inventory.json` (site root, committed)

Same envelope as `sites/webmd_doctor/generated_asset_inventory.json`
(`schema_version`, `asset_count`, `total_bytes`, `note`, `assets`), rows carry
the brief's fields plus `bytes` and `seed`:

```json
{
  "schema_version": 1,
  "asset_count": 164,
  "total_bytes": 0,
  "note": "Synthetic imagery: scenes generated with fal-ai/flux/schnell (4 steps, per-slot seed derived from the slug) and faculty initials avatars drawn deterministically with Pillow 11.0.0. No text, no logos, no watermarks, no faces, no posters, no real landmarks, no real people. Regenerate with scripts/gen_images.py + scripts/gen_avatars.py; ships via the pinned Hugging Face tarball.",
  "assets": [
    {
      "path": "static/images/campus/campus-quad.webp",
      "bytes": 0,
      "sha256": "<hex>",
      "kind": "campus",
      "source_row": "campus-quad",
      "model": "fal-ai/flux/schnell",
      "prompt": "<the exact prompt string sent>",
      "seed": 1092614210,
      "generated_on": "2026-09-14"
    }
  ]
}
```

`source_row` is the seed-DB identity the slot was built from: a
`colleges.slug` / `research_centers.slug` / `faculty.slug`, a
`<category>-<variant>` key, or the fixed campus scene key.
`kind` ∈ `campus | college | research | news | event | faculty`.
Avatars carry `"model": "pillow-initials-11.0.0"`, `"prompt": null`, `"seed": null`.

### 5.2 `sites/berkeley/check_generated_assets.py`

Mirrors `sites/webmd_doctor/check_generated_assets.py` in shape and severity,
and is invoked by `scripts/check_assets.sh` (which already runs any site's
`check_generated_assets.py` when both files exist) and by the Docker build.
It fails closed on, in order:

1. missing/short envelope, `schema_version != 1`, `asset_count != len(assets)`,
   duplicate path;
2. any `path` that is absolute, contains `..`, or is outside the six managed
   roots;
3. extension/kind agreement (`faculty` → `.png`, everything else → `.webp`);
4. **coverage**: files under those six roots (excluding `.gitkeep`) must equal
   the declared set exactly — a missing file and an undeclared file both fail;
5. per-file `bytes` and `sha256`;
6. a full decode of every file checking format, **planned dimensions**
   (`1024×768` / `256×256`) and the §9.3 letterbox test;
7. the §9.1 OCR pass **only under `--ocr`**. It is off by default because it
   costs roughly ten minutes over 82 scenes, and `scripts/check_assets.sh` calls
   this script for every site — a build step that pauses for ten minutes with no
   output reads as a hang. `tests/test_generated_assets.py` is where the OCR pass
   runs permanently, with its positive control.

The Docker image installs no `pytesseract` and no OpenCV, so in the image steps
1–6 run and the OCR step is not reachable at all. §9's full QA is a
developer-time pass, run by `gen_images.py` during generation and by the test
module afterwards.

### 5.3 `sites/berkeley/.requires-images`

```
UC Berkeley requires its generated scene imagery and faculty avatars
(static/images/{campus,colleges,research,news,events,faculty}/) from the pinned
Hugging Face archive.
```

`scripts/check_assets.sh` promotes `static/images` from a warning to a hard
failure when this file exists.

### 5.4 Dockerfile gate

```dockerfile
# UC Berkeley's generated imagery ships in the pinned asset bundle while its
# SQLite seed stays build-generated from tracked source. The inventory gate
# enforces exact coverage + per-file SHA-256 + decode of all 164 generated images
# (same contract as the webmd_doctor / compass / walmart inventories).
RUN python3 /opt/WebSyn/berkeley/check_generated_assets.py
```

The existing `RUN cd /opt/WebSyn/berkeley && rm -rf instance instance_seed &&
PYTHONHASHSEED=0 python seed_data.py && rm -rf instance` is unchanged, and
`.build-generated-seed` keeps its meaning for the seed only.

### 5.5 `sites/berkeley/tests/test_generated_assets.py`

* `check_generated_assets.verify() == 164` when the bundle is present, and a
  skip (not a failure) when `static/images/` is empty — the same
  "verify when present" pattern `tests/test_integration.py` already uses,
  because a fresh clone has no images until `scripts/fetch_assets.sh` runs;
* no undeclared files under the six roots;
* every `<img src>` in the rendered surface set (the `SURFACE_PATHS` + per-row
  detail routes `tests/test_answer_leaks.py` enumerates) maps to a file that
  exists on disk, via a Flask test client;
* every file decodes and matches its planned dimensions;
* the §9.1 OCR pass and the §9.2 face pass, each with a positive control so the
  detector is demonstrated to be able to fire (§9.3).

## 6. Deviations from the brief, and why

**6.1 Departments (30 rows) have no image family.** The brief lists department
cards and detail headers as photo locations, but the slot model in (b) has no
department family and department rows carry no `focus_areas`-like field to
build a distinct subject from — 30 more prompts would be `{name}` +
`{description_160}` over a generic building. Instead a department renders its
**parent college's** scene, which is what the page's own heading does:
`departments.html` groups every card under `<h2>…{{ college.name }}</h2>`
(line 16–17). Net effect: covered as the brief asks, at 14 files instead of 44.

**6.2 `Academics` news rows fall back to the `campus-life` family.** The app
publishes exactly seven news categories (`app.py:384`) and the listing's
category chips render those seven; the seed's one `Academics` row is not in the
app's taxonomy. Adding an eighth family costs 3 images for 1 article. The row
renders the `campus-life` image and alt text that still names its own category.

**6.3 Programmes, search, auth, error pages: no imagery.** `/programs` is an
83-card text grid whose upstream equivalent is also text-first, the brief's
slot model has no programme family, and programme cards are the surface several
answer-leak tasks (1, 12, 16, 20, 27, 28) read.

**6.4 Faculty avatars are Pillow initials, not FLUX portraits** — per the
brief; recorded because it is the one place where the inventory carries rows
with `"prompt": null`.

**6.5 Hero images are decorative (`alt=""`).** On `index.html` and the
`<section>` page headers the image sits behind a heading that already names the
page; a non-empty alt would make a screen reader announce the section twice.
Every other `<img>` carries a non-empty alt built from its seed row.

**6.6 Events are unoccupied (see §3.2).** The brief permits small back-view
figures; the model could not hold that for the `event` family (4 of 6 sampled
slots showed faces to camera). Making them `empty` costs nothing visually — an
unoccupied venue is a normal way to photograph one — and removes the failure
mode rather than retrying against it.

**6.7 Two seeds collide across kinds.** `seed_for` keys on the slot slug, so
`news:arts-1` and `event:arts-1` share a seed (likewise `arts-2`; the other
category slugs do not overlap between the two families). They carry different
prompts and so produce different images; the collision is harmless and
deterministic, and changing the key now would invalidate every accepted row.

## 7. Answer-leak safety

`tests/test_answer_leaks.py` scans rendered HTML for every UNIQUE answer fact
outside its task's discovery route, and scans `templates/*.html` for the same.
Every alt expression in §2 is built from fields the page **already renders as
text** on the same surface, so no alt introduces a token the sweep was not
already seeing:

| family | alt | why it is safe |
|---|---|---|
| B college | `{{ college.name }}` | college names are `GENERIC_VALUES` and already on `/academics` |
| B (department cards) | `{{ dept.college.name }}` | same, and already the group heading |
| C research | `{{ center.name }}` | centre names are catalogue data on `/research`; **not** director, founding year or focus areas — the graded answers for tasks 10, 23, 30, 31 |
| D news | `{{ article.category }} — Berkeley News` | category only; **never** `article.title`, the graded answer for task 19 and the event titles of task 6 |
| E events | `{{ event.category }} event at Berkeley` | category only; **never** `event.title` (tasks 6, 25) |
| F faculty | `Initials avatar for {{ member.name }}` | names are already on the directory card; the graded bindings are the profile visit plus interest tokens |
| A campus, page-header banners | `alt=""` | decorative, see §6.5 |

Two existing assertions bound this work:
`test_listing_surfaces_render_no_director_or_chair` (no listing may render
`Director:` or `Chair:`) and
`test_related_centre_cards_hide_director_founded_and_focus`, which inspects a
±700-character window around every `/research/<slug>` link — the new
`.card-img` in `research.html` sits **inside** that window, so its alt and any
nearby text must stay free of director/founded/focus. It does: the alt is the
centre name alone.

## 8. Cost and control

* 82 flux/schnell calls on the happy path. The pilot was 5 scenes (one per
  family) + all 82 avatars.
* A slot whose file exists **and** whose sha256, prompt and seed match its
  inventory row is skipped, so a re-run after a partial failure costs only the
  missing calls.
* Transport errors retry with exponential backoff (3 attempts, 2/4/8 s); a 4xx
  that is not 429 aborts immediately rather than burning the budget.
* `FAL_KEY` is read from the environment and never printed, logged, or written
  to the inventory — the prompt, model and seed are the only request fields
  recorded.

## 9. Automated QA, and what it does not catch

Every generated scene is checked immediately after download, **before** it is
written into the inventory. A failure re-runs the same slot at the next attempt
seed (§3.4), two attempts maximum; a slot still failing after that is written
with `"qa": "flagged"` and listed for human review rather than silently
accepted. Both checks are offline and need no key.

### 9.1 OCR pass

`pytesseract`, when importable, at 1× and 2× upscale over `--psm 3` and
`--psm 11`, counting alphabetic tokens of **≥4 characters at confidence ≥ 50**.
A count ≥ 3 flags the image.

Both numbers come from measurement. The first pass used (3 chars, confidence
40) and flagged six clean scenes on fragments like `aif`, `hea`, `iii`, `iti`,
`mao`, `own`, `the`, `says` — every one of them three characters, produced by
tesseract reading foliage, stone cladding and mown grass. The floor was raised
to sit above that noise; a rendered headline or a wordmark clears it easily
(§9.3).

And stated plainly: **this does not reliably detect legible text at all.** Two
measured misses, both found by eye rather than by the pass:

* `research/bair.webp` carried a legible warning placard that tesseract scored
  at confidence 0;
* `colleges/chemistry.webp` carries the word **`STCK`** in large red capitals
  across a window — unmistakably legible when the card is rendered — and the
  pass returns **zero tokens** for it at every setting (`--psm 3` yields
  nothing at all; 6 and 11 yield only single characters). The glyphs are large
  but low-contrast against a bright, busy background, and tesseract's layout
  analysis never isolates them.

So the honest summary is: the pass runs, it has a positive control that proves
it *can* fire on clean rendered text, and it misses real text in this bundle.
It is a tripwire of unknown sensitivity, not a text guarantee. What actually
bounds text is the prompt's negative list plus the §9.5 by-eye review — which
is what caught `STCK`.

### 9.2 Face pass

OpenCV Haar `haarcascade_frontalface_default.xml` (offline, shipped inside
`opencv-python-headless`), single-scale, at **calibrated** settings:

```python
detectMultiScale(scaleFactor=1.1, minNeighbors=10, minSize=(40, 40))   # 1x only
```

The OpenCV defaults (`1.05 / 6 / (24,24)`, over a 1× and 2× copy) were tried
first and **rejected on measurement**: on an empty quad with no person in it
they returned 7 boxes, and 6 on an empty laboratory — every one of them on tree
foliage or mown grass, and most of them from the 2× pass. A gate that flags a
clean image cannot gate anything. The table below is the calibration, taken on
the five pilot scenes:

| scaleFactor | minNeighbors | minSize | upscales | false positives |
|---|---|---|---|---|
| 1.05 | 6 | (24, 24) | 1×, 2× | **15** |
| 1.1 | 10 | (40, 40) | 1× | **0** |
| 1.1 | 12 | (48, 48) | 1× | 0 |
| 1.2 | 12 | (48, 48) | 1× | 0 |
| 1.1 | 15 | (60, 60) | 1× | 0 |

The most sensitive zero-false-positive row is the one shipped. `minSize=(40,40)`
is deliberate: a face large enough to be *recognisable* in a 1024×768 frame is
far larger than 40 px, and the small distant figures the `people` suffix asks
for are exactly what this gate must **not** flag.

**This gate is a coarse net, not the enforcement it was hoped to be.** Measured
on the full scene bundle (51 images), not assumed:

| scaleFactor | minNeighbors | minSize | upscales | detections | images hit |
|---|---|---|---|---|---|
| 1.1 | 10 | (40, 40) | 1× | 1 | 1 |
| 1.1 | 8 | (20, 20) | 1× | 2 | 2 |
| 1.05 | 8 | (20, 20) | 1×, 2× | **76** | **32** |
| 1.05 | 12 | (24, 24) | 1×, 2× | 32 | 17 |

It cannot separate a small distant face from photographic texture. At the
settings that find the real crowds in the `people` slots (the last two rows) it
returns dozens of boxes on foliage, stone and grass; at the shipped
low-false-positive setting it is **also a false negative** — the one box it
returns on `colleges/natural-resources.webp` is on grass beside a tree, while
the students with plainly visible faces in that same frame are not detected at
all, because they are smaller than `minSize`.

So, plainly: the cascade catches a large, centred, face-forward subject (it
detects the control at every row above) and it does **not** reliably catch the
small and profile faces this plan actually cares about. It is a cheap tripwire,
not a guarantee.

What the "never a recognisable face" rule actually rests on is therefore:

1. **The prompt.** The `people` suffix was tightened after this measurement —
   from "a few students seen from behind or at a distance" to "at most two or
   three people far away in the middle distance walking away from the camera,
   backs turned, faces completely hidden, no crowds, no visible faces" — because
   the first wording produced crowds with clear faces (measured, not suspected).
   This is the primary control.
2. **The contact sheet** (§9.4), reviewed by eye, which is the only check here
   that can actually see a small profile face.

The same honesty applies to §9.1: the OCR gate is a large-legible-text detector
that is known to miss small fixture labels.

### 9.3 Letterbox pass

Deterministic, no dependency beyond NumPy: take the top and bottom 2% of rows
and compute the mean pixel value of each band. Both near-black means the
provider drew a wider aspect inside the 4:3 canvas, which reads as a broken
image in a card.

This was found by eye, not by a gate — three of the first 82 scenes
(`news/campus-life-1`, `news/campus-life-2`, `news/science-1`) came back with
black bars — and was then turned into a check. It runs in
`check_generated_assets.py` (fails the build), in `gen_images.qa_report`
(a failed frame is retried at the next seed), and in `gen_images.is_accepted`,
so a letterboxed file that predates the gate is regenerated on the next run
instead of needing a hand-maintained list.

### 9.4 Positive controls

Both detectors are exercised against committed synthetic controls, so a green
run proves the check can fire rather than proving nothing was tested:

* **OCR control** — an image with rendered text must flag.
* **Face control** — `tests/face_control.png`, a 512×384 frontal
  portrait **generated by the same FLUX model with a deliberately face-forward
  prompt** (so it is a synthetic face, not a real person's photograph), must
  yield exactly one box. It does, at every row of the calibration table; at the
  shipped settings the box is `(128, 68, 273, 273)`.

If OpenCV or `pytesseract` is absent the corresponding pass reports itself
untested and the field is recorded as `null` rather than as a pass — a missing
detector must never read as a clean result.

### 9.5 The residual gap, and how it is covered

OCR cannot see small labels; the face cascade cannot see profiles; and neither
gate would have caught the black bars that §9.3 now checks for. The residual
gap is covered by eye: a contact sheet of every generated scene is rendered for
human review (`gen_images.py --contact-sheet`), and each family was sampled and
inspected before the images were wired into templates. This is stated in the
README rather than presented as a clean automated bill of health.

The by-eye pass found and fixed, in order: a seated person in a research
interior; crowds with faces to camera in the `event` family (which moved to
`empty`, §3.2); a framed portrait in a faculty-office scene (the anti-wall-art
motif clauses); the three letterboxed frames; and — on the contact sheet built
for review — the word `STCK` in large red capitals on
`colleges/chemistry.webp`, which every automated gate had passed.

The sheet is produced by `gen_images.py --contact-sheet` (default
`scripts_dev/contact_sheet.png`, six columns, filename under each thumbnail) and
can be rebuilt for a subset with `--sheet-only <stems>` after a partial
regeneration.
