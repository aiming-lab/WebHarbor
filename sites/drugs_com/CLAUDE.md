# drugs_com — WebHarbor mirror site

Flask mirror of drugs.com at port **40016**. Covers pharmaceutical drug information: lookup, interaction checking, pill identification, conditions, news, and user accounts.

## Quick start

```bash
# Build and run (from repo root)
./scripts/build.sh webharbor:dev
docker run -d --rm --name wh-test -p 8209:8101 -p 49016:40016 webharbor:dev

# Verify
curl -s http://localhost:8209/health | python3 -m json.tool   # control plane
curl -so /dev/null -w "%{http_code}" http://localhost:49015/   # should print 200

# Logs
docker logs wh-test --tail 50
docker exec wh-test cat /tmp/websyn_drugs_com.log

# Reset to seed state (byte-identical)
curl -X POST http://localhost:8209/reset/drugs_com
docker exec wh-test md5sum \
  /opt/WebSyn/drugs_com/instance/drugs_com.db \
  /opt/WebSyn/drugs_com/instance_seed/drugs_com.db
# Both hashes must match: bfc94f8ff61fbbd553ae496217588bad
```

## Architecture

### Models (`app.py`)

| Model | Key fields |
|-------|-----------|
| `Drug` | `slug`, `generic_name`, `brand_names`, `drug_class_id`, `availability` (Rx/OTC), `csa_schedule`, `pregnancy_risk`, `rating`, `review_count` |
| `DrugClass` | `name`, `slug`, `description` |
| `DrugImage` | `drug_id`, `imprint`, `shape`, `color`, `dosage_form` |
| `DrugInteraction` | `drug_a_id`, `drug_b_id`, `severity` (major/moderate/minor), `description` |
| `DrugReview` | `drug_id`, `user_id`, `rating` (1–10), `title`, `body` |
| `Condition` | `name`, `slug`, `description` |
| `NewsArticle` | `title`, `category`, `body`, `published_at` |
| `SavedDrug` | `user_id`, `drug_id` (My Med List) |
| `User` | `email`, `username`, `password_hash` |

### Key routes

| URL pattern | Template | Notes |
|-------------|----------|-------|
| `/` | `index.html` | Homepage with featured drugs and news |
| `/<slug>.html` | `drug_detail.html` | Drug detail (canonical) |
| `/drug_information.html` | `drug_az.html` | A-Z index |
| `/drug-interactions` | `interaction_checker.html` | Interaction checker (canonical) |
| `/pill-identifier` | `pill_identifier.html` | Pill identifier (canonical) |
| `/drug-classes/` | `drug_classes.html` | Drug class browser |
| `/drug-classes/<slug>/` | `drug_class.html` | Single drug class |
| `/conditions/` | `conditions.html` | Conditions A-Z |
| `/condition/<slug>/` | `condition.html` | Single condition |
| `/news/` | `news.html` | News index with category filter |
| `/search` | `search.html` | Drug/class/condition search |
| `/my-med-list` | `my_med_list.html` | Saved drugs (auth required) |

Flask uses the **last** `@app.route` decorator as the canonical URL for `url_for()`. Alias routes are placed first.

`app.url_map.strict_slashes = False` — all routes accept trailing-slash variants.

### Pill images

Rendered as inline SVGs via the `_pill_svg.html` macro — no external image files needed for the benchmark. Real pill photos live at `static/images/pills/<slug>.jpg` (HuggingFace asset); a `pill_image_exists` Jinja filter falls back to the SVG macro when the file is absent.

## Seed database

- **Location**: `instance_seed/drugs_com.db` (gitignored — sourced from HuggingFace)
- **MD5**: `bfc94f8ff61fbbd553ae496217588bad`
- **Contents**: 251 drugs · 748 reviews · 76 interactions · 103 pill images · 68 conditions · 80 news articles · 12 users

All `seed_*()` functions gate on an already-populated DB (early-return if rows exist) so `seed_database()` is idempotent and the reset invariant holds.

## Benchmark users

| Username | Email | Password | Notes |
|----------|-------|----------|-------|
| alice_j | alice.j@test.com | TestPass123! | Primary test user |
| bob_c | bob.c@test.com | TestPass123! | Secondary |
| carol_d | carol.d@test.com | TestPass123! | Secondary |
| david_k | david.k@test.com | TestPass123! | Secondary |

**Alice's seeded state** (task-critical — do not change):
- Med list: ibuprofen, metformin, atorvastatin (NOT lisinopril — task 14 asks to add it)
- Reviews: ibuprofen 9/10, lisinopril 7/10, hydrochlorothiazide 10/10

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
- Authenticated actions (My Med List — read and write)

## HuggingFace assets

Assets are packaged as `drugs_com.tar.gz` in the `ChilleD/WebHarbor` dataset (PR #13).

To repack and upload:
```bash
# From repo root
./scripts/extract_assets.sh /tmp/wh-assets drugs_com
hf upload ChilleD/WebHarbor /tmp/wh-assets/drugs_com.tar.gz drugs_com.tar.gz \
  --repo-type dataset --create-pr
```

To pull assets locally before building:
```bash
./scripts/fetch_assets.sh drugs_com
```
