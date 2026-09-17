# Rotten Tomatoes mirror

Rotten Tomatoes is the 22nd WebHarbor site and runs on container port `40021`. The site contains 270 source-backed movie records, 3,852 credited people, 23 TV records, 19 feature records, local images, and four synthetic benchmark accounts.

## Source and runtime model

- `data/source_catalog.json` records the official Rotten Tomatoes movie/detail and cast-and-crew source URLs, capture timestamps, capture hashes, normalized movie facts, credits, and expected image hashes.
- `data/homepage.json`, `data/tv_catalog.json`, and `data/feature_catalog.json` are validated source snapshots.
- HTTP requests read SQLite and local assets. They do not read the source JSON or fetch remote content at runtime.
- The Docker build generates `instance_seed/rotten_tomatoes.db` deterministically from tracked source documents. Populated databases validate immutable catalog and content state before serving.
- `static/images` and `static/external_cache` are required from the Hugging Face revision in `.assets-revision`.
- `download_source_images.py` downloads only exact catalog image URLs, enforces origin/type/size restrictions, normalizes with pinned Pillow settings, and checks generated SHA-256 values against the catalog.

The four local account identities, credentials, ratings, watchlists, and reviews are explicitly synthetic benchmark state. Seeded public review display names are not treated as Alice's private reviews or deletable account content.

## Tasks and verification

Seven tasks are defined in `tasks.jsonl`: four read-only comparison tasks and three state-changing account tasks. Production verifiers derive expected facts and state transitions from the supplied initial SQLite database. They enforce task identity, completed execution, same-origin navigation, required filters/searches, click transitions, final-answer binding, schema integrity, complete read-only database equality, and exact bounded changes for stateful tasks.

Run tests from the repository root:

```bash
uv run --with-requirements sites/rotten_tomatoes/requirements.txt python -m unittest discover -s sites/rotten_tomatoes/tests -v
cd agent_demo && uv run python -B -m unittest discover -s ../sites/rotten_tomatoes/verify -p 'test_*.py' -v
```

Build and run through the repository-level `scripts/build.sh` and `websyn_start.sh` workflow. Use `/reset/rotten_tomatoes` on the control service before each independent task attempt.
