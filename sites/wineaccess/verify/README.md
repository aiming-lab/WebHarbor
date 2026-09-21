# WineAccess deterministic task verifiers

The official entrypoint is:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py \
  --run_dir /absolute/path/to/run --verifier True
```

Each run must contain `trajectory.json`, `initial.db`, and `after.db`. Capture
consistent SQLite backups of the isolated WineAccess runtime immediately before
and after the task. The verifier opens those snapshots read-only. It never reads
a running container or substitutes the seed for a task's actual initial state.
The caller is responsible for capturing snapshots; the browser agent does not
have access to the site's database by default. Explicit `--initial_db` and
`--after_db` overrides are available when invoking a wrapper directly.

Trajectories carry the matching `task_id`, `start_url`, ordered steps with `url`
and recorder-observed `page_text`, and the natural-language `final_answer`.
`agent_demo/agent.py` records the same DOM representation used by the browser
agent. Existing `observed_text` / `observed_text_before` fields are also accepted.
Thoughts, action parameters and self-reported extracted answers are not treated
as page observations. Query filters and category routes are both supported;
URL query substrings and different origins do not prove a page visit.

The grader checks the exact requested database transition and preserves all
unrelated rows. Read tasks require unchanged snapshots. Checkout binds the
new order to the initial cart, prices, totals, prefilled address, inventory and
observed confirmation number. Saved memberships must be active. It also checks
that the required products/account/content were observed in the browser.

Answer checking accepts ordinary prose, short answers, lists and common
paraphrases. State-only tasks do not require hidden keywords or a fixed output
format. Comparison tasks do not require unrequested dates or prices, but any
reported values must be accurate. Pairing task 15 asks for the suggested
pairings, so all three are checked. The parser is bounded to these benchmark
facts, entity/value relationships and tested polarity/comparison constructions;
it is not a general semantic judge. Recorder observations are trusted evidence,
not a cryptographic anti-tampering mechanism. The LLM judge remains a separate,
optional secondary evaluation.

Run route, state, answer, navigation and archive-independence regression tests:

```bash
python3 -m unittest discover -s sites/wineaccess/verify -p 'test_*.py' -v
```

Tests use an isolated temporary Flask runtime seeded from the downloaded archive;
they do not write to a running preview. Full browser recordings and the Docker
build/reset checks are separate validation steps.
