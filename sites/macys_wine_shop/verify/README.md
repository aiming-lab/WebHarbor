# macys_wine_shop — reviewer grading contract

Reviewer-authored grading artifacts for the 30 benchmark tasks, same contract as the
hardened reviewer suites (`sites/merriam_webster/verify/`, `sites/instructure/verify/`).

## Layout

- `verify_lib.py` — shared fail-closed harness. Trajectory identity gates (task_id,
  `agent_done`, non-empty answer, same-origin loopback URLs, decodable PNG screenshots),
  navigation gates (scored search with sort, collection listings with metafield facet
  filters `filter.p.m.drinks.*` and sort, product detail pages, cart, three-step checkout,
  account order history, Wine Club tabs, Wine 101 blog, gift card), tolerant answer
  matching (accent-folded phrases, thousands groups, `$`-money, percent forms), SQLite
  snapshot validation bound to the frozen seed (schema `7fdbd7fc…`, 19-table counts, rows
  digest `44d5827f…`, benchmark user identities) and the fail-closed CLI runner. LLM
  helpers are advisory-only; verdicts are decided with `--no_llm True`.
- `verify_0.py` … `verify_29.py` — one verifier per task, ground truth HARDCODED inside
  each file (never in `tasks.jsonl`). Read-only tasks require every table row-identical
  before/after; stateful tasks (13/15/16/24) require exactly the allowed row delta
  (a guest cart row / a placed order with its items and the consumed cart rows / a new
  user + order) and nothing else.
- `append_rubrics.py` — string-insertion appender for `tasks.jsonl`: the five contributor
  keys stay byte-identical, `verifier_path` + `judge_rubric` are inserted before the
  closing brace, and no answer key is ever written.
- `tests/` — contract tests (see below).

## Usage

```bash
# grade a run (from the repo root; container fetch only used when DBs are not in run_dir)
python3 sites/macys_wine_shop/verify/verify_0.py --run_dir runs/00 --no_llm True

# full contract test sweep (seed fetched from the review container, cached)
cd agent_demo && uv run python -m pytest ../sites/macys_wine_shop/verify/tests -q
```

## Contract test coverage

- honest PASS ×30 — task 3/5/6 fixtures simulate the compliant post-fix state (the live
  mirror's collection `sort_by` currently has no effect on the rendered order — see the
  review report F1 — and task 27's fixtures simulate the gift-card amount selector the
  live mirror does not render yet, F2), exactly like the instructure T24 precedent:
  the verifier grades the repaired site correctly without needing any change once the
  contributor ships the fix.
- no-op FAIL ×30 (first failure `final_answer_nonempty`).
- wrong-answer FAIL ×30.
- shortcut FAIL ×30 (every task's required surface is beyond the homepage).
- read-only tamper FAIL ×26 (a mutated after-DB).
- stateful mismatch FAIL ×4 (self-reported success, unchanged DB) + wrong-delta FAIL ×3.
- package tampering FAIL ×7 (task_id mismatch, off-site URL, missing screenshot,
  non-done trajectory, tampered seed, unavailable DB, missing trajectory).

Live evidence (wh-mws-review-evidence/): 26/30 honest live runs PASS against the
independent review container `wh-rev-macys_wine_shop`; 30/30 no-op FAIL; 4 honest live
runs FAIL fail-closed on the documented site defects (3/5/6 — collection sort no-op;
27 — gift-card amount selector missing); 5/5 live adversarial probes (wrong answer ×2,
shortcut ×2, state mismatch) correctly FAIL.

## Ground-truth freeze notes

- Prices, case contents, awards, Wine Info rows, Wine Club facts, order history, cart
  rules ($14.95 shipping under 6 bottles / $2.95 processing / 3-bottle checkout minimum /
  free shipping at 6+) are frozen against the tracked `source_data.json` snapshot seed
  (see `.build-generated-seed`); the physical seed file may differ between sqlite builds
  but the verifier binds to the logical row digest.
- Task 16's third bottle is the agent's choice ("add 1 more bottle of any wine"): the
  verifier requires the after-DB cart to hold exactly 3 bottles with ≥2 Valanda
  Tempranillo and checks the reported total against the DB-derived total.
- Task 24 accepts any order quantity ≥3 for the Closed Window Pinot Noir (the site's
  checkout minimum) and checks the reported total against the placed order row.
- Accent tolerance: product names captured with diacritics (Alquería, Montañero, Rosé)
  are accent-folded by the matcher so "Alqueria" matches "Alquería".
