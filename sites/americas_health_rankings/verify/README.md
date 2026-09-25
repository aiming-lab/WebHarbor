# America's Health Rankings deterministic verification

Run through `agent_demo/eval_judge.py --run_dir <run> --verifier True`.
Each task has a `verify_N.py` entrypoint; ground truth stays in this directory.
The task file contains requests and answer-free rubrics.

A complete run needs a finished trajectory, real decoded PNG screenshots,
one consistent mirror origin, and an initial/after database pair. Supply both
`initial.db` and `after.db` snapshots for reproducible offline grading. When neither
is supplied, the existing `--container` fallback reads the seed and live databases
from that container. Partial snapshot pairs fail closed. The initial rows must match the reviewed
seed; state changes must preserve unrelated records. The primary verdict is
binary and makes no LLM calls.

Revised tasks require the requested comparison pages and facts as well as the
original task outcome. Natural sentences and labeled comparisons are supported;
JSON is not required. Numeric/entity parsers are bounded and do not claim general
semantic understanding. Screenshots and recorded text establish evidence presence,
not cryptographic proof of interaction; reviewers inspect actual browser recordings.

Run `python -m unittest discover -s sites/americas_health_rankings/verify -p 'test_*.py'`
from the repository root with the site's seed assets present. Synthetic controls
are separate from real browser review evidence. The latter lives outside the
site tree and is documented in `review-reports/pr163-americas_health_rankings.md`.
