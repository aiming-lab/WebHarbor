# Drugs.com local benchmark fixture

This site is the 43rd WebHarbor environment and runs on container port `40042`. It is a deterministic local software-evaluation fixture, not the official Drugs.com service or a medically reviewed reference.

## Data contracts

- `app.py` is the tracked source for local fixture records and contains no runtime or seed-build network fetch.
- `seed_data.py` builds a staged candidate, validates canonical counts, SQLite integrity, foreign keys, schema/catalog digests, byte count, and SHA-256, then atomically installs `instance_seed/drugs_com.db`.
- `seed_manifest.json` binds the canonical database, catalog, schema, and seed version.
- `content_inventory.json` documents fixture-family provenance status.
- `asset_inventory.json` binds 13 archived DailyMed product labels, 13 authentic packaging images and a build-time catalog (27 files). HTTP handlers read the seeded database, not the catalog JSON. These supplements do not verify the remaining fixture families. Pill visuals remain visibly labeled synthetic SVG descriptor diagrams, not photographs or identification evidence.
- `.build-generated-seed` causes the Docker build to regenerate the seed after pinned HF assets are extracted.

## Verification

Use the repository's `uv`-managed environment and run:

```bash
pytest -q sites/drugs_com/tests sites/drugs_com/verify
```

The 21 task verifiers require the trusted evaluator-configured origin (`http://localhost:40042` by default), successful browser actions, decoded nonblank screenshot transitions, canonical immutable database snapshots, task-specific workflow evidence, and bound noncontradictory natural answers. See `verify/README.md` for revised task wrappers and explicit preview-origin configuration.
