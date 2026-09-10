# WebMD Doctor mirror

Offline Flask mirror of `https://doctor.webmd.com/` (branded "WebMD Care" upstream). In the 25-site registry it is site index 24 and runs on container port `40024`. Every doctor, practice, hospital, address, phone number, NPI, review and user account is deterministic synthetic benchmark data; only the site chrome mirrors upstream.

## Runtime

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r sites/webmd_doctor/requirements.txt
cd sites/webmd_doctor && PYTHONHASHSEED=0 ../../.venv/bin/python seed_data.py   # writes instance_seed/, static/images/{avatars,posters}/
PORT=40024 ../../.venv/bin/python app.py
```

The Docker build regenerates `instance_seed/webmd_doctor.db` plus the Pillow avatars (226) and video poster frames (91) from `seed_data.py`; the site ships no Hugging Face assets (`.build-generated-seed`). `seed_metadata` version `webmd-doctor-v1`, `EXPECTED_COUNTS` and a foreign-key check reject partial or incompatible state, and every seed function is gated as a whole so `/reset/webmd_doctor` and `docker restart` leave the DB byte-identical.

## Seeded rows

| Model | Rows | Model | Rows |
|---|---|---|---|
| doctors | 226 (202 within 40 mi of Newark, DE 19711 + 24 in Baltimore, MD) | locations | 348 |
| specialties | 10 | conditions / procedures / expertise_areas | 40 / 30 / 40 |
| doctor_conditions / doctor_procedures / doctor_expertise | 1677 / 1252 / 686 | insurers / insurance_plans / doctor_insurances | 12 / 28 / 2274 |
| cities / city_zips | 8 / 24 | hospitals / practices | 12 / 30 |
| reviews | 1206 | doctor_perspectives | 1582 |
| certifications / licenses / education | 296 / 316 / 567 | awards / doctor_languages | 50 / 351 |
| users | 4 | saved_providers / appointment_requests / user_reviews | 4 / 1 / 1 |

Benchmark accounts: `alice.j`, `bob.c`, `carol.d`, `david.k` `@test.com`, password `TestPass123!`.

## Routes

`/`, `/results` (deterministic term parser + conjunctive filters, Best Match / Distance / Average Rating / Number of Ratings), `/doctor/<slug>-overview` (tab aliases 301), `/doctor/<slug>/bookappointment` (Enhanced only, login required), `/doctor/<slug>/save`, `/doctor/<slug>/review`, `/providers/specialty[/<spec>[/<state>[/<city>]]]`, `/hospitals[/<state>]`, `/hospital/<slug>`, `/grouppractices[/<state>]`, `/practice/<slug>`, `/choice-awards`, `/choice-awards/awardrecipients?award-class=`, `/reviews-guidelines`, `/login`, `/signup`, `/logout` (POST), `/account/saved`, `/account/saved/<slug>/remove`, `/account/appointments`, `/health`.
