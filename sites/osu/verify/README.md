# Ohio State verifier suite

The OSU mirror has 20 deterministic task verifiers, one per row in `sites/osu/tasks.jsonl`.

Each verifier requires the expected task ID, a non-empty answer, same-origin navigation on the configured loopback origin, the task-specific path/query/click sequence, affirmative answer facts bound to the requested entity, and a complete unchanged SQLite database. All current OSU tasks are read-only.

Run the regression suite from the repository root:

```bash
uv run --with Flask==3.1.0 --with Flask-SQLAlchemy==3.1.1 --with Flask-WTF==1.2.2 --with Flask-Bcrypt==1.0.1 --with Flask-Login==0.6.3 --with email-validator==2.2.0 python -m unittest sites.osu.verify.test_verifiers sites.osu.verify.test_environment_quality sites.osu.verify.test_app -v
```

The tests include positive cases and controls for answer-only runs, wrong task IDs, external-origin URLs, database mutations, missing filters, negated answers, swapped comparison values, and missing or altered image files.

## Image assets

The mirror uses 19 photographs crawled from official Ohio State web properties. `sites/osu/image_sources.json` records each source page, source URL, dimensions, alt text, and source/output SHA-256. `sites/osu/fetch_images.py` reproduces the normalized WebP files. The binaries are distributed as `osu.tar.gz` from the Hugging Face asset revision pinned in `.assets-revision`.
