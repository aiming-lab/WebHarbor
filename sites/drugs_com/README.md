# Drugs.com local benchmark mirror

This directory contains the Drugs.com-style WebHarbor environment. It is registered as the 43rd site on container port `40042` and is intended only for deterministic software evaluation. It is not the official Drugs.com service and its fixture records are not medical guidance.

## Runtime data

`app.py` contains the tracked source fixtures and Flask application. `seed_data.py` builds a candidate database without touching the active instance or known-good seed, validates it without network access, and atomically installs it. The seed is accepted only when the `seed_metadata` version is `drugs-com-source-v3`, canonical static table counts match, SQLite integrity and foreign keys pass, and the catalog/schema digests match `seed_manifest.json`; the builder additionally verifies the canonical database byte count and SHA-256.

The seed contains 246 medication records, 105 drug classes, 69 conditions, 379 drug-condition links, 104 pill-description records, 76 drug-drug interactions, 11 explicitly drug-keyed food/alcohol interaction records, 80 simulated news records, 716 simulated review records, 15 saved-medication records, and 12 fixture users. Pill-description rows are rendered as visibly labeled synthetic diagrams and are not real product images or identification evidence. `content_inventory.json` records the provenance status and runtime treatment of every fixture family.

Run a deterministic rebuild with:

```bash
cd sites/drugs_com
PYTHONHASHSEED=0 uv run python seed_data.py
```

## Assets

The original pill descriptors still use explicitly synthetic inline SVGs. Separately, `/official-labels` contains 13 selected DailyMed product-label supplements and 13 authentic packaging-label images. They are not Drugs.com articles or pill photographs. `asset_inventory.json` binds all downloaded files, including archived SPL XML and the build-time catalog. `scripts/recover_dailymed.py` is an explicit recovery tool, never a runtime/build network dependency. HTTP handlers read the `daily_med_label` table.

The replacement HF archive is merged through [HF #101](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/101) and the standard archive-root correction [#102](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/102). The immutable pin is `555a9aa0b02946a8bdf873ba1d59902b71564a07`; `assets-manifest.json` binds its archive bytes and extracted tree. The archive contains `drugs_com/static/images/dailymed/` and `drugs_com/static/external_cache/dailymed/`; the SQLite seed remains build-generated. The earlier 134-byte archive and rootless #101 intermediate must not be used for this revision. See [INTEGRATION_REPORT.md](INTEGRATION_REPORT.md) for full fetch/build, 43-site health/reset and browser/grading evidence.

## Tests

From the repository root with the site dependencies installed:

```bash
pytest -q sites/drugs_com/tests sites/drugs_com/verify
```

The application tests cover routing, validation, authentication, ownership, state mutation, seed integrity and reset behavior. The verifier tests execute every task verifier against positive and adversarial trajectories. Task answers can be ordinary prose, bullets or simple tables; JSON is optional. Bounded deterministic checks bind facts to entities, properties and units and reject tested contradictions. See `verify/README.md` for parsing limits, saved-snapshot priority and trusted preview-origin configuration.
