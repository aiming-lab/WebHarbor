# PhET review regression suite

The mirror is a frozen 2026-09-13 catalogue. Official metadata can gain translations
without invalidating its deterministic counts. Activities and accounts are benchmark
fixtures, not PhET teacher submissions. The registry assigns port 40035.

Use Python 3.12 and fetch the immutable per-site asset pin first (Bash 4+):

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install Flask==3.1.0 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 Flask-WTF==1.2.2 Flask-Bcrypt==1.0.1 bcrypt==5.0.0 pytest==9.1.1 beautifulsoup4==4.15.0 playwright==1.63.0 huggingface_hub==1.32.0
./scripts/fetch_assets.sh phet_simulations
python scripts/check_site_registry.py
python -m pytest sites/phet_simulations/tests/test_review_regressions.py -q
playwright install chromium
python sites/phet_simulations/verify/tests/record_regressions.py --output /tmp/phet-runs
python sites/phet_simulations/verify/tests/adversarial_matrix.py --runs /tmp/phet-runs --output /tmp/phet-matrix
```

An installed Chrome can be selected with `--chrome /absolute/path/to/chrome`.
The browser driver copies the app into a temporary directory and uses a fresh
browser context and a restored seed for every task. It never changes a running
user environment. Save and registration requests are issued through actual UI
forms, with CSRF enabled. DB snapshots are frozen around each task.

These are **scripted regression executions with fixed expected answers**, not
independent agent exploration or independent blind review. The matrix's modified
trajectories are marked `adversarial_fixture` and never presented as agent runs.

Primary evidence is the viewport screenshot after an explicit scroll to relevant
content (release dates, translation counts, related simulations, regional language
cards and save confirmations). Full-page screenshots are supplementary. Each run
records the logical site port and actual local origin so host-port mapping is
explicit. The root manifest hashes every captured artifact.

The deterministic suite covers 18 positive executions, 108 negative cells (no-op,
wrong answer, no navigation, forbidden/missing write, same-count edit, external
navigation) 9 targeted counterexamples (wrong labels, version, winner, query, role or incomplete
navigation), and 7 legitimate alternatives. The latter include optional empty
completion text for task 14, as its rubric permits.

The regression tests also cover homepage rails, filter semantics and preservation,
all 279 enumerated public GET URLs, seed byte identity, genuine learning goals,
card answer leakage, CSRF, account isolation, malformed inputs and exact DB deltas.
The browser sweep tests 21 pages at widths 1440, 768 and 390 plus mobile navigation.

The suite does not replace the full repository Docker build, 36-site health sweep,
or `/reset-all` test. Those must use the global plus per-site asset pins from this
checkout. A prior PR's build badge is not validation of this tree.
