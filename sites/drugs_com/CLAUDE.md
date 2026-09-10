# Drugs.com local benchmark fixture

This site is the 25th WebHarbor environment and runs on container port `40024`. It is a deterministic local software-evaluation fixture, not the official Drugs.com service or a medically reviewed reference.

## Data contracts

- `app.py` is the tracked source for local fixture records and contains no runtime or seed-build network fetch.
- `seed_data.py` builds a staged candidate, validates canonical counts, SQLite integrity, foreign keys, schema/catalog digests, byte count, and SHA-256, then atomically installs `instance_seed/drugs_com.db`.
- `seed_manifest.json` binds the canonical database, catalog, schema, and seed version.
- `content_inventory.json` documents fixture-family provenance status.
- `asset_inventory.json` declares zero runtime media assets. Pill visuals are visibly labeled synthetic SVG descriptor diagrams and are not real product images or identification evidence.
- `.build-generated-seed` causes the Docker build to regenerate the seed after pinned HF assets are extracted.

## Verification

Use the repository's `uv`-managed environment and run:

```bash
pytest -q sites/drugs_com/tests sites/drugs_com/verify
```

The 21 task verifiers require the exact `http://localhost:40024` origin, successful ordered browser actions, decoded nonblank screenshot transitions, canonical immutable database snapshots, task-specific workflow evidence, and bound noncontradictory answers.
