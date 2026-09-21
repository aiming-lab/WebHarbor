# Amtrak deterministic grading contract (natural-answer revision)

The 18 wrappers call `contract.py`; `answer_contract.py` validates typed answers
and `checkout_state.py` validates saved bookings. Ground truth stays in reviewer
code, never in agent-facing task definitions. No verifier calls an LLM.

## Evaluate saved evidence

```bash
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
python -m pytest sites/amtrak/verify/tests -q
```

A run needs `trajectory.json`, referenced PNG screenshots and saved `initial.db`
/ `after.db`. Explicit snapshot paths are also accepted by `verify_N.py`.
Missing snapshots fail closed; grading never silently substitutes a running
container's current state. Output: `{task_id, pass, reason, evidence[]}`, exit 0/1.

Trajectories must identify the task and local origin, terminate with
`agent_done`, contain decodable screenshots, and record visible page text as
`observed_text_before` / `observed_text_after` with `url` / `url_after`.
The shared agent records these explicit fields while retaining the existing
pre-action `observed_text` field for other sites. Earlier Amtrak recordings that
used `observed_text` for post-action content remain supported.
Thoughts/answers/action parameters
do not substitute for observed pages. Legacy runs need new recordings.

## Natural answers; structured expectations stay internal

Tasks use normal, concise user instructions. There is no required JSON schema,
field naming convention, sentence template or verbatim policy quotation.
Ordinary prose, bullets and Markdown tables are accepted. The final answer must
still report every requested fact, including comparisons and arithmetic.

`natural_answer.py` normalizes claims into local entity/property/value checks:
fares remain bound to the fare family, account statistics to the named account,
station baggage to the particular station and polarity, and policies to their
timing, scope and refund destination. Contradictory extracted values are rejected;
a correct-looking reference number does not repair an incorrect claim.
Currency/number formatting, ordinary date/time variants, written-out whole
numbers and tested policy paraphrases are accepted. Task 0 requires total elapsed
time rather than on-board minutes.

This parser is deliberately bounded and deterministic, not a general semantic
entailment model. Its tests cover multiple independently written formulations,
not just the replay formatter. Unrecognized/ambiguous wording fails a named
checkpoint; broaden coverage with positive/negative regression cases when a
legitimate missed paraphrase is found, rather than requiring users to imitate
the parser. A configured secondary LLM judge is separate and should assess the
meaning without imposing hidden syntax rules.

Previous structured recordings remain supported for backward compatibility by
`answer_contract.py`; this internal representation is not advertised as a
required task output. Browser, fixture-integrity and precise state checks apply
equally to natural and structured answers. Missing snapshots still fail closed.

## Tasks and state

| Tasks | Required outcome |
|---|---|
| 0–4 | Sorted/filtered searches, round-trip/multi-city selection and fare/room comparison |
| 5 | Alice's Denver booking versus current Flexible quote including fee/increase |
| 6 | Public booking lookup versus fastest direct Business quote/increase |
| 7 | Alice/Bob balances, YTD points, status credits and balance difference |
| 8 | Only Alice's preferred-station fields become SEA |
| 9 | Ordered Cascades stops and baggage at each station |
| 10 | Coast Starlight advisory recommendation plus cheapest sleeper comparison |
| 11 | Denver advisory track, westbound train/time on service-date board, station baggage |
| 12 | CHI–DEN Flexible fare and route |
| 13 | SAC–SJC Saver/Flexible search-filter comparison and upgrade |
| 14 | ANA/SBA baggage, ordered Surfliner stops and help cutoff |
| 15 | Baggage policy, departure and calculated baggage deadline |
| 16 | Refund help search plus fastest-service Saver/Flexible fare/policy comparison |
| 17 | One direct Business booking for adult Alice Jordan, default mock checkout |

Tasks 5, 6, 7, 9, 10, 11, 13, 14, 15 and 16 combine meaningful evidence and
comparison rather than prescribed extra clicks. Schedule dates are the
synthetic train's origin **service date**, not necessarily its departure
calendar date at an intermediate station.

Snapshots require the expected 22-table schema. Initial logical rows are pinned
to the reviewed seed; catalog rows cannot change. Read tasks preserve every
mutable table, including search logs. Task 8 permits only two preference fields.
Task 17 requires exactly one added booking, segment, passenger, ticket, payment
and reward activity: exact foreign keys/ownership; catalog-derived Business fare
plus fee; passenger identity; ticket/trip/fare consistency; exact reward deltas;
all existing rows and unrelated fields preserved. Any valid direct Business
train is eligible: pricing is derived, not tied to the replay's selected train.

## Regression evidence

`tests/test_verify_matrix.py` and `tests/test_natural_answers.py` use synthetic trajectories and copied snapshots
for all tasks, malformed packages, wrong fields, positive equivalents,
fixture tampering, collateral writes and checkout deltas. These are not browser
completions.

`tests/live_matrix.py` with `v2_drives.py` drives Playwright and extracts
answers from rendered pages. Set `AMTRAK_BASE`, `AMTRAK_RESET_CMD`,
`AMTRAK_SEED_DB`, `AMTRAK_INSTANCE_DB` and a fresh `--out_dir`.
The reset command must own its isolated runtime, never a user's preview.
See the module docstring for the optional container snapshot hook.
`natural_responses.py` is only a response formatter for the scripted UI replay, not a grader dependency or required answer template. Real UI positives and synthetic controls are separate. Scripted replay is
not an independent LLM agent; the optional LLM judge is a separate evaluation.
