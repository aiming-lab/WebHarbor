# Walmart Careers mirror

This directory contains an offline Flask mirror modeled on `https://careers.walmart.com`. In the 25-site registry it runs on container port `40023`. All jobs, stores, requisition identifiers, user accounts, saved roles and applications are deterministic synthetic benchmark data.

## Runtime

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r sites/walmart_careers/requirements.txt
PYTHONHASHSEED=0 .venv/bin/python sites/walmart_careers/seed_data.py
PORT=40023 WALMART_CAREERS_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  .venv/bin/python sites/walmart_careers/app.py
```

The Docker build removes any downloaded Walmart seed and regenerates `instance_seed/walmart_careers.db` from `catalog_source.py`. `seed_metadata` version `walmart-careers-v2`, expected row counts, foreign keys and tracked tests reject partial or incompatible state.

## Assets and provenance

- `asset_inventory.json` covers the 35 HF-managed runtime images by path, bytes and SHA-256.
- `tracked_asset_inventory.json` covers all tracked runtime icons and the font.
- `provenance.json` classifies catalog and content sources.
- `check_tracked_assets.py` and the root inventory checker run during the Docker build.

Seventeen image records contain independently recovered direct asset URLs. Eighteen records retain the source page recorded for the contributor's captured derivative because the original PR did not preserve the exact direct asset URL. Those records are marked `source_kind: source_page`; they are not represented as direct-download provenance.

## Validation

```bash
python -m pytest sites/walmart_careers/tests sites/walmart_careers/verify/tests -q
python sites/walmart_careers/check_tracked_assets.py
python scripts/check_asset_inventory.py sites/walmart_careers
```

The deterministic task verifiers derive target sets from the supplied versioned initial database. See `verify/README.md` for package, workflow, screenshot and state constraints.
