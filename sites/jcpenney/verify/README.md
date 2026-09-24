# jcpenney deterministic grading

Run the primary grader from the repository root:

```bash
python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
```

Every task has a `verify_N.py` entrypoint. `verify_lib.py` validates task identity,
completion, local-origin navigation, decodable screenshots and frozen SQLite
snapshots; `reviewed.py` adds the reviewed outcome contracts. `review_common.py`
checks entity-bound facts, monetary amounts and exact row preservation. The
initial snapshot must match the build-generated seed. Store `initial.db` and
`after.db` with the trajectory; snapshots take precedence over live databases.

Instructions, rubrics and verifiers describe the same outcome. Equivalent prose,
bullets and currency spacing are supported. No browser action-count threshold is
used to decide success. Deterministic language parsing remains bounded: unusual
paraphrases may need rubric review. The optional LLM judge is secondary.

The synthetic fixtures under `tests/fixtures` derive from reviewed browser paths
and database outcomes, with tiny placeholder screenshots. They are grading
controls, not UI or independent-agent evidence. Tests cover positive answers,
missing/stale/off-site evidence, wrong answers, account preservation and state
no-ops. Purchase controls additionally reject old-order changes, incorrect line
ownership and quantity. Run `pytest sites/jcpenney/verify/tests` after building its seed.

Every state task preserves unrelated users, orders and catalog rows. Purchases
require the requested owner, items, totals and confirmation. Read-only tasks
must not mutate the database. Browser review recordings remain outside the
source tree and are linked in the reviewer PR.
