# drugs_com — WebHarbor mirror site

Flask mirror of drugs.com at port **40016**. Covers pharmaceutical drug information: lookup, interaction checking, pill identification, conditions, news, and user accounts.

## Contribution status

- **Code PR**: `aiming-lab/WebHarbor` #9, branch `feat/drugs-com` in fork `boyugou/WebHarbor`. Open, mergeable, no conflicts with `main` at last check.
- **Assets PR**: `ChilleD/WebHarbor` (HuggingFace dataset) discussion #39. Open. `.assets-revision` is pinned to `refs/pr/39` until it merges.
- **Current seed DB md5**: `d3d228f3fc0b3b880e149ac35550e3c5` (this value moves every time seed data changes — verify the file on disk if any documentation disagrees).
- The code side has been through multiple rounds of review (functional + security + benchmark-task-quality + data-integrity), each round's findings verified against the codebase before acting and then fixed. See "Answer-leak guardrails" and "OpenFDA content fetch" below for the two most consequential fixes, and the PR's own comment history for the full list.
- After the code and asset reviews are complete: merge the assets PR, re-pin `.assets-revision` to `main` (or the merge commit), then merge the code PR. See the repo-root `AGENTS.md`/`CONTRIBUTING.md` for who performs those maintainer-owned steps.

## Quick start

```bash
# Build and run (from repo root)
./scripts/build.sh webharbor:dev
docker run -d --rm --name wh-test -p 8209:8101 -p 49016:40016 webharbor:dev

# Verify
curl -s http://localhost:8209/health | python3 -m json.tool   # control plane
curl -so /dev/null -w "%{http_code}" http://localhost:49016/   # should print 200

# Logs
docker logs wh-test --tail 50
docker exec wh-test cat /tmp/websyn_drugs_com.log

# Reset to seed state (byte-identical)
curl -X POST http://localhost:8209/reset/drugs_com
docker exec wh-test md5sum \
  /opt/WebSyn/drugs_com/instance/drugs_com.db \
  /opt/WebSyn/drugs_com/instance_seed/drugs_com.db
# Both hashes must match: d3d228f3fc0b3b880e149ac35550e3c5
```

## Architecture

### Models (`app.py`)

| Model | Key fields |
|-------|-----------|
| `Drug` | `slug`, `generic_name`, `brand_names`, `drug_class_id`, `availability` (Rx/OTC), `csa_schedule`, `pregnancy_risk`, `avg_rating`, `review_count` |
| `DrugClass` | `name`, `slug`, `description` |
| `DrugImage` | `drug_id`, `imprint`, `shape`, `color`, `strength`, `manufacturer` |
| `DrugInteraction` | `drug_a_id`, `drug_b_id`, `severity` (major/moderate/minor), `description` |
| `DrugReview` | `drug_id`, `user_id`, `rating` (1–10), `title`, `body` |
| `Condition` | `name`, `slug`, `description` |
| `NewsArticle` | `title`, `category`, `body`, `published_at` |
| `SavedDrug` | `user_id`, `drug_id` (My Med List) |
| `User` | `email`, `username`, `password_hash`, profile names, persisted account/subscription preferences |

### Key routes

| URL pattern | Template | Notes |
|-------------|----------|-------|
| `/` | `index.html` | Homepage with featured drugs and news |
| `/<slug>.html` | `drug_detail.html` | Drug detail (canonical) |
| `/drug_information.html` | `drug_az.html` | A-Z index |
| `/drug-interactions` | `interaction_checker.html` | Interaction checker (canonical) |
| `/pill-identifier` | `pill_identifier.html` | Pill identifier (canonical) |
| `/drug-classes.html` | `drug_classes.html` | Drug class browser |
| `/drug-classes/<slug>` | `drug_class.html` | Single drug class |
| `/conditions.html` | `conditions.html` | Conditions A-Z |
| `/conditions/<slug>` | `condition.html` | Single condition |
| `/news/` | `news.html` | News index with category filter |
| `/search` | `search.html` | Drug/class/condition search |
| `/my-med-list` | `my_med_list.html` | Saved drugs (auth required) |

Flask uses the **last** `@app.route` decorator as the canonical URL for `url_for()`. Alias routes are placed first.

`app.url_map.strict_slashes = False` — all routes accept trailing-slash variants.

### Auth and CSRF

`/login` and `/register` do real bcrypt-checked authentication (matching every
other site in the repo) — there is no auto-login shim. `CSRFProtect` is
enabled; every `<form method="post">` carries a `csrf_token` field. Two routes
that are called from both a real form AND from JavaScript
(`/my-med-list/toggle`, `/<slug>/review/<id>/helpful`) are **not** exempt —
their JS call sites carry the token too (`X-CSRFToken` header for the
JSON-body call, an appended `FormData` field for the other), so both paths are
actually checked. Only `/api/interaction-check` is `@csrf.exempt` — it's a
pure-JSON endpoint that is not referenced by any template (dead code; no
current task depends on it), so this is a deliberate, verified-safe exemption
rather than an oversight. It accepts at most 20 unique, bounded drug names so
its pairwise comparison work cannot be amplified into an unbounded request.

The Flask signing key comes from `DRUGS_COM_SECRET_KEY` when supplied and is
otherwise generated randomly into the runtime `instance/.secret_key`. A normal
restart keeps sessions and anonymous-vote identity stable; a full reset rotates
the key with the runtime instance. Never use a public source-code fallback.
Logout is POST-only and CSRF-protected. Bcrypt
inputs are capped at 72 bytes so bcrypt 5 cannot turn an oversized password
into a server error.

### Pill images

Rendered as inline SVGs via the `_pill_svg.html` macro — no external image files needed for the benchmark. Real pill photos live at `static/images/pills/<slug>.jpg` (HuggingFace asset); a `pill_image_exists` Jinja filter falls back to the SVG macro when the file is absent.

## Seed database

- **Location**: `instance_seed/drugs_com.db` (gitignored — sourced from HuggingFace)
- **MD5**: `d3d228f3fc0b3b880e149ac35550e3c5`
- **Contents**: 246 drugs · 104 drug classes · 716 reviews · 76 interactions · 103 pill images · 69 conditions · 80 news articles · 12 users

The top-level `seed_database()` gates the complete seed pipeline on an already-populated DB, so none of its helper phases run after a reset and the byte-identical invariant holds.
SQLite foreign-key enforcement is enabled on every SQLAlchemy connection.
Review writes use an upsert on `(drug_id, user_id)`. Med-list changes accept
an idempotent desired state, retain a serialized legacy-toggle fallback, and
use `ON CONFLICT DO NOTHING`, so simultaneous valid requests cannot become
unique-constraint 500s or ambiguous toggles. Helpful votes are validated,
deduplicated per user/session, and updated atomically; account email updates
catch unique races, and per-user preference writes are serialized. A user's
`public_reviews=false` preference excludes their review text, condition
suggestions, counts, rating distributions, and averages from public views
while leaving their own account/edit views available.

### OpenFDA content fetch — the match-verification guard

`fetch_openfda_label(generic)` calls the live `api.fda.gov` label-search
endpoint to source real `uses`/`warnings`/`dosage`/`side_effects` text per
drug at seed time, falling back to a generated (`synthetic_content()`)
template when nothing is found. **The search endpoint does fuzzy/tokenized
matching, not exact matching** — it has been observed returning a
completely unrelated drug's label for a query with no exact hit (e.g.
querying `polyethylene glycol` returns a label whose own
`openfda.generic_name` is `["NAPROXEN"]`). `_openfda_label_matches()` checks
the returned label's generic and active-substance names against the query,
including rejecting multi-ingredient labels for monotherapy queries, before
accepting it; a mismatch is treated as "not found" and
falls through to `synthetic_content()`. **Do not remove this check** — without
it, a reseed can silently give an arbitrary drug another drug's entire
detail-page content, and because the fetch is a live network call, which
drugs are affected is not deterministic across reseeds.

## Benchmark users

| Username | Email | Password | Notes |
|----------|-------|----------|-------|
| alice_j | alice.j@test.com | TestPass123! | Primary test user |
| bob_c | bob.c@test.com | TestPass123! | Secondary |
| carol_d | carol.d@test.com | TestPass123! | Secondary |
| david_k | david.k@test.com | TestPass123! | Secondary |

Benchmark-account state is task-critical. Do not change seeded saved drugs,
reviews, or preferences without reviewer coordination; ground-truth values are
intentionally omitted from source documentation.

## Benchmark tasks

21 tasks in `tasks.jsonl` (`Drugs.com--0` through `Drugs.com--20`), covering:
- Drug detail lookup (drug class, brand names, availability, CSA schedule)
- Drug interaction checker (2-drug and 3-drug, severity)
- Pill identifier (by imprint, shape, color)
- Drugs A-Z browsing
- Drug class navigation (Statins, Benzodiazepines, Fluoroquinolones)
- Condition browsing (diabetes, hypertension)
- News reading (category filter, latest article)
- User reviews and ratings
- Authenticated actions (task 14: sign in, then read the My Med List page — this specific task is read-only; the underlying add/remove-from-med-list feature exists and works but no task currently exercises the write side)

### Answer-leak guardrails — do not reintroduce

These were found and removed because they let a task be answered without
following the navigation path its wording describes. If you add a homepage
widget, an index-page summary, or a search sidebar, check it against this
list:
- The homepage does **not** list individual article titles for the "New
  Drug Approvals" category (only a category link) and excludes that
  category from its general "Latest Medical News" feed — both used to
  leak task `--11`'s answer (the latest article's title) directly.
- `/drug-classes` does **not** list member-drug names per class on the
  index page (only name + count + link) — used to leak "list N drugs in
  class X" tasks (e.g. `--16`) without opening the class page.
- `/search` does **not** have a "Popular for `<query>`" sidebar listing
  drug names for a matched condition/class — used to leak `--6`/`--9`/`--20`
  the same way. (Plain search *results* legitimately showing matching drug
  names when you search a class/condition term by name is fine — that's
  the literal mechanism several tasks tell you to use, not a leak.)
- Homepage featured-drug cards do **not** show rating/review aggregates; those
  values belong on the detail/reviews pages required by task `--12`.
- `.drug-card`/`.exact-match-card` blocks in `search.html` show only the
  drug name and a link — no `drug_class`, `brand_names`, `csa_schedule`,
  `avg_rating`/`review_count`, or description snippet. These are shown on
  the actual detail page, which requires a click-through.

## HuggingFace assets

Assets are packaged as `drugs_com.tar.gz` in the `ChilleD/WebHarbor` dataset. The
packer below is macOS-safe (plain `tar` would embed `._*` AppleDouble files).

**There is already an open HF PR for this site's assets** — discussion #39
(https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/39, ref
`refs/pr/39`). If the seed DB changes again before that PR merges, push a new
commit onto the SAME PR ref rather than opening a second one:
```bash
# From repo root
./scripts/extract_assets.sh /tmp/wh-assets drugs_com
hf upload ChilleD/WebHarbor /tmp/wh-assets/drugs_com.tar.gz drugs_com.tar.gz \
  --repo-type dataset --revision refs/pr/39
```
Only use `--create-pr` (which opens a brand-new PR) if #39 has already merged
and you're starting a fresh asset update.

To pull assets locally before building:
```bash
./scripts/fetch_assets.sh drugs_com
```
`.assets-revision` is currently pinned to `refs/pr/39` (not `main`) as a
temporary measure — see that file's own header comment for why, and bump it
once #39 merges.
