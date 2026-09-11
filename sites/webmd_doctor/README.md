# WebMD Doctor mirror

Offline Flask mirror of `https://doctor.webmd.com/` (branded "WebMD Care" upstream). In the 25-site registry it is site index 24 and runs on container port `40024`. Every doctor, practice, hospital, address, phone number, NPI, review and user account is deterministic synthetic benchmark data; only the site chrome mirrors upstream.

## Runtime

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r sites/webmd_doctor/requirements.txt
./scripts/fetch_assets.sh webmd_doctor                                          # static/images/{avatars,posters}/ from the HF tarball
cd sites/webmd_doctor && PYTHONHASHSEED=0 ../../.venv/bin/python seed_data.py   # writes instance_seed/webmd_doctor.db
PORT=40024 ../../.venv/bin/python app.py
```

The Docker build regenerates `instance_seed/webmd_doctor.db` from `seed_data.py` (`.build-generated-seed`); the Pillow initials avatars (226) and video poster frames (91) under `static/images/` ship in the pinned Hugging Face tarball (`.requires-images`) and are regenerated locally with `PYTHONHASHSEED=0 python seed_data.py --write-images` (byte-stable PNGs: fixed compression, no ancillary chunks). `seed_metadata` version `webmd-doctor-v1`, `EXPECTED_COUNTS` and a foreign-key check reject partial or incompatible state, and every seed function is gated as a whole so `/reset/webmd_doctor` and `docker restart` leave the DB byte-identical.

## Seeded rows

| Model | Rows | Model | Rows |
|---|---|---|---|
| doctors | 226 (202 within 40 mi of Newark, DE 19711 + 24 in Baltimore, MD) | locations | 348 |
| specialties | 10 | conditions / procedures / expertise_areas | 82 / 62 / 40 |
| doctor_conditions / doctor_procedures / doctor_expertise | 1800 / 1316 / 674 | insurers / insurance_plans / doctor_insurances | 12 / 28 / 2258 |
| cities / city_zips | 8 / 24 | hospitals / practices | 12 / 30 |
| reviews | 1227 | doctor_perspectives | 1582 |
| certifications / licenses / education | 307 / 295 / 595 | awards / doctor_languages | 50 / 363 |
| users | 4 | saved_providers / appointment_requests / user_reviews | 7 / 1 / 1 |

Benchmark accounts: `alice.j`, `bob.c`, `carol.d`, `david.k` `@test.com`, password `TestPass123!` (public by design; the scrypt hashes are hardcoded in `seed_data.py` and validated at build time). Gender distribution: 102 female / 103 male / 21 non-binary.

## Routes

`/`, `/results` (deterministic term parser + conjunctive filters, Best Match / Distance / Average Rating / Number of Ratings), `/doctor/<slug>-overview` (tab aliases 301), `/doctor/<slug>/bookappointment` (Enhanced only, login required), `/doctor/<slug>/save`, `/doctor/<slug>/review`, `/providers/specialty[/<spec>[/<state>[/<city>]]]`, `/hospitals[/<state>]`, `/hospital/<slug>`, `/grouppractices[/<state>]`, `/practice/<slug>`, `/choice-awards`, `/choice-awards/awardrecipients?award-class=`, `/reviews-guidelines`, `/login`, `/signup`, `/logout` (POST), `/account/saved`, `/account/saved/<slug>/remove`, `/account/appointments`, `/_health` (with `/health` kept as a legacy alias).

## Synthetic identifier policy (NPI)

The 226 seeded NPIs are benchmark identifiers, not real provider numbers. Each is a 10-digit individual-range value (leading `1`) whose check digit satisfies the CMS rule (Luhn mod 10 over `80840` + the first nine digits), and each was verified as **not assigned** against the NPPES full dissemination file of 2026-08-09, the weekly files through 2026-09-06, and the deactivated-NPI report of 2026-08-10 (9,786,956 unique values). The registry-verified list is embedded in `seed_data.py` (`VERIFIED_NPIS`) and re-checked at every seed build; the site RNG stream is independent of the list, so slugs and images are unaffected. As with any unassigned identifier, a future NPPES assignment could eventually collide; the whole site is labelled synthetic on every page.

## Known deviations from upstream

- 226 doctors (above the 200 guideline) so every distance bucket and filter value keeps >= 20 rows within the default 40-mile radius; non-binary gender seeded at 21.
- Pillow-drawn initials avatars and gradient poster panels instead of photography (no real people); all website URLs use the reserved `.example` TLD and are unreachable offline.
- Free-text search for a doctor's NAME returns the upstream-style zero-result state by design (upstream behaves the same); every task routes through specialty, hub, filter or award pages.
- Specialty-by-state and specialty-by-city hub pages are thin (1 to 14 doctors), mirroring upstream's per-city structure.
- Review sorting/filtering/search controls, maps, "List/Claim your practice", password recovery and footer policy links are labelled unavailable in the mirror.
- Menus and filter popovers require JavaScript for the overlay behavior; without JavaScript they render as static expanded lists (progressive enhancement), and select-driven forms expose a `<noscript>` submit button.
- Form fields that benchmark tasks require the agent to provide (patient type on the booking widget, rating and criteria on the review form, all search and filter values) arrive empty: no preselected radios, and the location `<select>` lists the provider's offices in seeded order with no `selected` attribute.
- Aggregate rating columns (`avg_rating`, `ratings_count`) are immutable synthetic summary values; `ratings_count` intentionally exceeds the written-review count (ratings without text), so aggregates are not recomputable from the `reviews` table alone.
- Seed database bytes are reproducible within the pinned toolchain (Python 3.12, Pillow 11.0.0, image SQLite); SQLite file bytes can differ across SQLite versions with identical logical content. The reset contract (`instance/` == `instance_seed/`) holds byte-for-byte in every environment.
