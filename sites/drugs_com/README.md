# Drugs.com local benchmark mirror

This directory contains the Drugs.com-style WebHarbor environment. It is registered as the 25th site on container port `40024` and is intended only for deterministic software evaluation. It is not the official Drugs.com service and its fixture records are not medical guidance.

## Runtime data

`app.py` contains the tracked source fixtures and Flask application. `seed_data.py` builds a candidate database without touching the active instance or known-good seed, validates it without network access, and atomically installs it. The seed is accepted only when the `seed_metadata` version is `drugs-com-source-v2`, canonical static table counts match, SQLite integrity and foreign keys pass, and the catalog/schema digests match `seed_manifest.json`; the builder additionally verifies the canonical database byte count and SHA-256.

The seed contains 246 medication records, 105 drug classes, 69 conditions, 379 drug-condition links, 104 pill-description records, 76 drug-drug interactions, 11 explicitly drug-keyed food/alcohol interaction records, 80 simulated news records, 716 simulated review records, 15 saved-medication records, and 12 fixture users. Pill-description rows are rendered as visibly labeled synthetic diagrams and are not real product images or identification evidence. `content_inventory.json` records the provenance status and runtime treatment of every fixture family.

Run a deterministic rebuild with:

```bash
cd sites/drugs_com
PYTHONHASHSEED=0 uv run python seed_data.py
```

## Assets

The runtime uses database-backed inline SVG pill renderings. `asset_inventory.json` requires zero external runtime media files. A small Hugging Face archive exists only to preserve the repository-wide one-archive-per-site asset contract; the SQLite seed is generated during the Docker build and is not stored in that archive.

## Tests

From the repository root with the site dependencies installed:

```bash
pytest -q sites/drugs_com/tests sites/drugs_com/verify
```

The application tests cover routing, validation, authentication, ownership, state mutation, seed integrity and reset behavior. The verifier tests execute every task verifier against positive and adversarial trajectories. Each task question declares an exact JSON-only result schema so the deterministic verifier can reject duplicate, extra, missing, mistyped, contradictory, or out-of-domain answer fields without attempting open-ended natural-language interpretation.
