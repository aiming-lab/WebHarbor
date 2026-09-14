# Ohio State verifier suite

The OSU mirror has 20 deterministic task verifiers, one per row in `sites/osu/tasks.jsonl`.

Each verifier requires the expected task ID, a non-empty answer, same-origin navigation on the configured loopback origin, the task-specific path/query/click sequence, affirmative answer facts bound to the requested entity, and a complete unchanged SQLite database. All current OSU tasks are read-only. Ground truth lives only inside `verify_N.py` — `tasks.jsonl` has `verifier_path` + English `judge_rubric` rules, with no `answer` key.

Run the regression suite from the repository root:

```bash
python3 -m unittest discover -s sites/osu/verify/tests -v
```

The tests include genuine PASS cases and controls for no-op / empty-answer, answer-only knowledge shortcuts, listing-without-detail shortcuts, wrong task IDs, external-origin URLs, database mutations, missing filters, negated answers, swapped comparison values, and listing-page answer leaks. `sites/osu/verify/tests/` is excluded from the Docker image by `.dockerignore`.

## Image assets

The mirror uses 19 photographs crawled from official Ohio State web properties. `sites/osu/image_sources.json` records each source page, source URL, dimensions, alt text, and source/output SHA-256. `sites/osu/fetch_images.py` reproduces the normalized WebP files. The binaries are distributed as `osu.tar.gz` from the Hugging Face asset revision pinned in `.assets-revision`. The seed database is generated at image build time (`sites/osu/.build-generated-seed`).
