# WebMD deterministic grading

Run from the repository using the official entrypoint:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py \
  --run_dir /absolute/path/to/run --verifier True
```

Each run must archive `initial.db` before actions and `after.db` after completion,
using SQLite backup or a stopped database copy. These must be the run's state,
not the mutable preview or a newly copied seed. Both are opened read-only; a
missing/corrupt snapshot fails. The primary grader never contacts Docker or an
LLM. `--initial_db` / `--after_db` can explicitly select alternative archived
snapshots when invoking a verifier directly. `--no_llm True` is retained as a
compatibility option; there is no live-container fallback.

`trajectory.json` needs the task ID, actual `start_url`, `final_answer`, and
ordered steps with observed `url`, `page_text`, and referenced screenshots.
The agent records DOM text with each stable page URL; scripted recorders may
use visible body text. Screenshots live in `screenshots/`; references may be
basenames or `screenshots/name.png`. An action target, query string, answer,
or screenshot without observed text does not prove navigation. Older runs
without text need recapture rather than invented evidence. The evidence is
trusted recorder output, not a cryptographic proof against forged traces.

Checks are independent: requested same-origin navigation and observed content;
precise state changes; and facts in the final answer. Condition-to-drug paths,
requested section/topic filters, checker symptom selections/results, and
account/profile transitions are required where the task requests them. Either
statin comparison order is accepted. Logout redirects home, so task17 checks
the password confirmation, logged-out page, login form, and authenticated Bob
profile in order. It does not require an impossible `/logout` page observation.

Read-only tasks preserve all DB rows. Registration adds exactly the requested
account with a verifiable password. Saving adds exactly the requested article
for Alice, preserving earlier saves. Password change alters only Bob's hash.
Existing reading history is preserved; the save task may add history for Alice
on observed article pages. Password verification requires bcrypt (declared and
locked in `agent_demo`); malformed hashes or missing dependencies fail closed.

Answer parsing is bounded to this frozen task set, not a general semantic
model. It supports common prose, labelled bullets/tables, dates, numeric words,
and equivalent time/dose units. It binds roles, quantity units, comparison
winners, and policy polarity; it rejects known contradictory formulations.
Unrecognized complex paraphrases can still fail. Add both a correct equivalent
and a plausible incorrect control when expanding coverage; do not require an
answer template. Ground truth stays in verifier code, not task prompts/rubrics.
A secondary LLM judge can be run separately with `eval_judge.py` default mode;
it does not change these primary results.

```bash
python -m unittest discover -s sites/webmd/verify/tests -v
```
