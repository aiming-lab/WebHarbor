# Cookpad mirror: sourced snapshot

This catalogue contains 60 Cookpad recipes and their corresponding source photos.
It replaces the earlier 180-entry catalogue, which contained generated recipes,
unrelated legacy data and a shared placeholder image.

Recipe titles, authors, ingredients, instructions, photos and available metadata
are recovered from the linked Cookpad Recipe JSON-LD. The build input and
provenance are in `source_catalog.json`; runtime handlers read SQLite only.
Saves mean BookmarkAction, not ratings or comments. Missing times/counts remain
unknown. Collections are locally curated navigation groups, not Cookpad taxonomy.
The four demo users and their lists, saved recipes and meal plans are explicitly
synthetic benchmark state. These local features do not sync to real Cookpad.

## Rebuild and assets

```bash
python sites/cookpad/seed_data.py --output /new/path/cookpad.db
python -m unittest discover -s sites/cookpad/tests -v
python -m unittest discover -s sites/cookpad/verify -v
```

Use the Docker Python 3.12 environment for reproducibility. The seed builder
refuses an existing destination. Runtime startup copies the shipped seed only
when the runtime is absent; it never regenerates or overwrites either database.
Restart preserves edits; control-plane reset restores the seed byte-identically.

Required HF bundle: `cookpad/instance_seed/cookpad.db` plus the 60 files named
by `source_catalog.json` and the two source brand images in `brand_assets.json`
under `cookpad/static/images/`. Source HTML is review
evidence, not a runtime dependency. HF PR #35 (original contribution) and #99
(reviewed replacement) are merged; `.assets-revision` pins the latter's immutable
merged revision and archive SHA-256. Fetch with `./scripts/fetch_assets.sh cookpad`.
Cookpad is appended at index 40 / port 40040, preserving existing site ports.

See `tools/recover_sources.py --help` for the provenance recovery tool. A fresh
recovery changes the snapshot and requires coordinated seed/task/rubric/verifier
review; do not silently replace counts in an established benchmark.
