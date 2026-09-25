# NVIDIA deterministic grading (repair002)

This directory keeps @DEM1TASSE's 20 entry-point names; the reviewer repaired the grading implementation. The original site contribution is attributed to @KaKituken. Grading uses only the Python standard library (PNG structural validation is implemented directly with `zlib`/`binascii`); it does not import Flask/app and does not call models, the network, or extra processes; the only optional subprocess call is `docker cp` for DB fetch (the same fallback as the other sites' verifiers in this repository).

## Invocation and output

```bash
# 1) Repository-documented path: agent_demo/eval_judge.py --verifier True passes only --run_dir
WH_CONTAINER=wh-review python3 -B sites/nvidia/verify/verify_0.py --run_dir /absolute/run

# 2) Explicit inputs (the four-input copy of native-ready backend.verify())
python3 -B sites/nvidia/verify/verify_0.py \
  --run_dir /absolute/phase-input \
  --initial_db /absolute/phase-input/initial.db \
  --after_db /absolute/phase-input/after.db
```

The CLI is fully consistent with the other sites' verifiers in this repository: `--run_dir` is required; `--initial_db`/`--after_db` are optional and default to `docker cp` of `instance_seed/nvidia.db` and `instance/nvidia.db` from the running container named by `--container` (default `$WH_CONTAINER` or `wh-review`); `--no_llm` is an accepted compatibility flag (grading is always deterministic). A failed `docker cp` is a structured INFRA, not a traceback.

- `run_dir` must contain `trajectory.json`; `task.json` is optional (the production recorder does not write it). When `task.json` exists it must equal, field by field, this task's definition in this checkout's `tasks.jsonl`, otherwise INFRA — stale tasks/rubrics cannot be silently accepted.
- The trajectory accepts either key set: (a) explicit/native-ready — `task_id`, `query`, `steps`, `final_answer`, each step a consecutive integer `step` plus `url`/`url_before`/`url_after`, optional `final_url`, `boundary_events`; (b) the production recorder (`agent_demo/agent.py`) — `task` (not `query`), `start_url`, each step `step`/`url`, no `task.json`, no `final_url`. When both keys appear they must both equal the canonical ques, otherwise INFRA.
- When `final_url` is absent, the fallback is the page where the run stopped: the last step's `url_after`, or that step's `url` if absent. T11 additionally requires that terminal page to be the local RTX 5080 purchase page.
- The no-action baseline is `steps=[]` with an empty answer.
- URLs are parsed by their actual origin and exact path/query; the port must be consistent within one run, but mapping changes between runs are allowed and the task file's 40028 is not enforced. Relevant-object evidence comes from the actually corresponding detail page, a comparison containing the target slug, a driver result containing the target row, or a news listing; `?q=/products/...` is not detail-page evidence.
- The single-site backend accepts only local loopback origins; `localhost`/`127.0.0.1`/`[::1]` on the same port are treated as the same loopback host (repair002, M9, because the harness's host spelling and port mapping are run details); the port must be consistent within one run, and cross-origin or non-loopback hosts, or boundary events, still FAIL. Missing/unreadable input, invalid JSON (including duplicate keys), ID/query/task mismatch, and schema/integrity/FK errors are INFRA.
- Screenshot evidence binding (repair002, H3): decodable PNG screenshots must exist under `run_dir`, minimum 320x200, maximum 8 MiB. If the trajectory names screenshot files (`screenshot_before`/`screenshot_after`/`screenshot`/`screenshot_path` — written by both the production recorder and native-ready), every named file must exist; otherwise the directory is scanned and the count must be >= min(steps, 2). Validation parses the PNG signature, every chunk's CRC, IHDR/IDAT zlib decompression, and scanline lengths with the standard library, so 1x1, truncated, or renamed non-PNG files FAIL (INFRA).
- SQLite is forced into `mode=ro` and `query_only`; the original application's full 10-table/column set and consistent before/after schemas are required. Missing DBs are not created, and there is no fallback to other containers/tasks.

stdout is always one JSON object: `task_id` for this task, `pass` a strict bool, `reason` an explanation, `evidence` a check summary.

| exit | meaning |
|---|---|
| 0 | normal PASS, `pass=true` |
| 1 | normal task FAIL, `pass=false` |
| 2 | INFRA_ERROR, `pass=false,error="INFRA_ERROR"`; the outer layer should report `success=false`, and it must not count as a valid negative case |

The comparison page accepts both the final UI's native GET `product=a&product=b` and the legacy `ids=a,b`; per the app's actual precedence the former overrides the latter, and the two parameter groups must not be merged to fabricate a product as displayed.

## Grading principles

- Information tasks: facts are taken from the explicit initial DB (T11's static technical/purchase facts are source-backed), with required relevant page/object evidence. Information matching uses model entities, values and units, comparison subject direction, version components, and complete dates; it is not substring matching. Reasonable formats are supported: case/whitespace/thousands separators, GB/GDDR 7, USD/dollars, W/watts, and clear date formats.
- Deterministic parsing supports concise factual sentences and explicit relations; it does not claim to understand arbitrary rhetoric or implication. Ambiguity or contradiction returns FAIL, keeping the original output for the independent head judge; there is no LLM fallback, and a missing LLM configuration must not turn into a task FAIL.
- Negation scope (repair002, H2): documentation-scope qualifiers such as "not a live release feed / frozen historical catalog" are exempted only for **T9/T10** (`predicates.driver_qualifier_scope` removes only the negation inside that phrase while preserving the full original text); the other 18 tasks exempt only comparisons unrelated to the target (other models, irrelevant metrics, variant names, PSU notes), and any targeted negation/uncertainty word FAILs (fail-closed). The boundary is pinned by the built-in regression `tests/test_driver_qualifier.py::test_other_information_task_not_relaxed`.
- T6's wording requires the comparison tool, and a single comparison must include both 5090/4090; T7 does not mandate a tool and may read the two detail pages separately. For T18, news/search listings that show dates are acceptable and details are not required (search evidence must contain a word token that actually appears in the article body/headline; purely numeric queries no longer count as evidence). T11 requires both technical-page and 5080 purchase-page evidence, ends on the local purchase page, with no fixed browsing order.
- State tasks: the DB is the authoritative record of the completed result; an English final answer or a login-page visit is not additionally required. New/deleted row IDs are bound to the same account and target, protecting every other wishlist/users/reviews/orders record. Only the simulated driver download counter's non-decrease is allowed as a harmless side effect; mistaken account/wishlist operations or extra orders are not harmless.
- Wishlist additions require the target not to exist before, and exactly one new row; T16 removes only Alice's target while preserving all other entries. T14 changes only Alice's country, preserving other fields. T15 requires a single new row satisfying Alice/Jetson/5-star/exact normalized title/non-empty body; `Not Incredible` FAILs. T19 adds only the specified email subscription, and that row's `topic` must be this store's GeForce list value.
- Wishlist write endpoints (repair002, M8): the site templates use `/wishlist/add/<id>` and `/wishlist/remove/<id>`, both idempotent (repeated submissions do not change state); the legacy `/wishlist/toggle/<id>` is kept for compatibility. Grading still requires exactly one new row and is not relaxed by endpoint idempotency.
- T16 historical correction: the original real login → account → detail-remove route would have been accepted by the original verifier; this repair does not exaggerate the original actual UI failure via simplified URL fixtures and instead grades directly on the accurate state.

## Task changes and fact sources

The 20 source IDs are kept. Only T5/T11/T12/T17 changed query semantics; the other 16 keep their original queries; all 20 task URLs were updated to 40028 and the rubrics updated to English FACT CHECKPOINTS. The rubric is for the grader only; the actor receives only ques, and this directory or the rubric must not be exposed to it.

- T5: Orin Nano Super **8GB developer kit** compared with Orin NX **16GB production module**; the two objects' memory and identity must be associated correctly. Normal product price tags are kept; difficulty is not created by deleting visible prices.
- T11: Blackwell, fifth-generation Tensor, fourth-generation RT; RTX 5080 **NVIDIA Marketplace / United States (en-us)** purchase information, staying local, with no external access or ordering.
- T12: the original 40-series lowest-price card becomes an addition to Alice's local Wishlist.
- T17: the mirror's frozen price, the cheapest Gaming with >=16GB, and the specific RTX 5060 Ti **16GB version** become an addition to Alice's local Wishlist; this is not a live retail-price conclusion.

T11 source: official `https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/`, captured offline 2026-09-09. Original HTML SHA256 `977dc25fd5586343e1e939bb67cae371a58b1d1df0e5d45c552eb7d55709c2fe`. The visible text includes "NVIDIA Blackwell Architecture / Fifth-Gen Tensor Cores / Fourth-Gen Ray Tracing Cores"; that page's 5080 "See All Buying Options" href is `https://marketplace.nvidia.com/en-us/consumer/graphics-cards/?...gpu=RTX%205080...`. The source supports only the entry point and region; it does not prove stock, price, or checkout. The private capture receipt, raw HTML, and reference hashes are stored in the review evidence area and are not delivered with the site source.

## Known deviation: rubrics contain answer tokens (repair002, M7)

In `tasks.jsonl`, 18 of the 20 tasks' `judge_rubric` states the graded values directly (for example `32 GB GDDR7`, `10,752`, `566.36`, `June 16, 2026`), while CONTRIBUTING.md's reviewer convention requires rubrics to state rules, not answers. Merged sites (for example `sites/osu`, `sites/ted`) show the same practice, so this is a conflict between existing repository practice and the documentation, not a definition deviation unique to this PR.

Disposition: the rubric's answer checkpoints are kept rather than rewritten into vague wording — the rubric is the LLM judge's (secondary grader's) checklist, and removing the values would directly weaken secondary grading; the deterministic verifier remains the primary grader, and its ground truth is fixed inside `sites/nvidia/verify/`, independent of the rubric. Note also: this repository's harness (`agent_demo/agent.py`) passes only `ques` to the model under test, and `judge_rubric` only enters `trajectory.json` for the judge, so the current path does not leak at runtime.

Release condition: either the repository decides uniformly whether rubrics may carry values (and CONTRIBUTING.md is corrected accordingly), or rubrics are changed to describe only the required fields/relations with values supplied by the verifier, and the evaluation side injects verifier facts into the judge context, to avoid weakening secondary grading.

## Mechanical regressions

Use a **separate copy** of the production assets or the designated full-schema seed, do not import the site, and write the output to a new directory outside the candidate source tree:

```bash
python3 -B sites/nvidia/tests/test_verifiers.py \
  --seed /absolute/nvidia/instance_seed/nvidia.db \
  --out /absolute/new-review-evidence-directory
```

Coverage includes each task's no-op, correct fixture, and dedicated near-miss, plus wrong account/target/delta, side effects, legitimate alternative navigation, format positives, and schema/identity INFRA. Per case, the input DB/task/trajectory/hash, SQL changes, command, stdout/stderr/exit, and input-unchanged checks are saved. Fixtures are mechanical evidence, not UI or native results; the real candidate seed, UI/native runs, and the independent head judge still need separate acceptance.

The CLI/input contract has its own regression suite pinning the invocation shape required by `agent_demo/eval_judge.py --verifier True` (only `--run_dir` plus the container fallback), the production recorder's trajectory key set, `--no_llm` compatibility, and structured INFRA on malformed inputs:

```bash
WH_CONTAINER=<running nvidia container> TEST_OUT=/absolute/outside/source/tree \
  python3 -B -m unittest discover -s sites/nvidia/tests -p 'test_verifier_contract.py'
```

## Grading-contract changes in the extended repair round (post-#107)

Every grading issue found by the last round's 20-task audit (`_wh_review_tools/pr107-audit/agent-{a,b,c}/summary.md`) was fixed in this round; each change matches semantics the rubric already required, and `tasks.jsonl` was not changed.

| Task | Change | Basis | Regression |
|---|---|---|---|
| T6 | `answers.cuda_compare()` rewritten as "comparison claim + count attribution" parsing: accepts the rubric's own phrasing (`… 5,376 more CUDA cores than … (21,760 versus 16,384)`), counts-first (`21,760 CUDA cores against 16,384 for the 4090, which is 5,376 more`), and trailing delta (`while the 4090 has 16,384; that is 5,376 more`); inverted subjects, wrong metric, wrong delta, equality claims, and swapped absolute counts still FAIL | audit agent-a `blocker` (9 of 21 naturally correct statements were misjudged) | `tests/test_verifiers.py` (`rubric-wording`, `trailing-delta`, `swapped-absolute-counts` + `NEAR[6]`), `agent-a/verifier-probe/probe-T6-*`, `t6-pass`, `t6-inverse` |
| T1 | `answers.measurements()` also recognizes unit-first spec-row phrasing (`CUDA Cores: 10,752`); the allowed unit set and value validation are unchanged (`Tensor Cores: 10,752`, `CUDA Cores: 11,752` still FAIL) | audit agent-a `medium` | `NEAR[1]`, `spec-row-echo`, `agent-a/verifier-probe/probe-T1-row_echo` |
| T3 | The answer must give both model and price (bare `$299` FAILs) | audit agent-a `low` | `bare-price-only`, `model-and-price`, `agent-a/verifier-probe/t3-bare_price_only` |
| T5 | Evidence must cover **both** products (a comparison containing both, or two detail pages); a single product/purchase page is no longer sufficient | rubric text "FAIL for … one-product-only evidence" | `one-jetson-page-insufficient`, `other-jetson-page-only-insufficient`, `both-jetson-details`, `agent-a/verifier-probe/T5-*` |
| T9/T10 | `predicates.driver_evidence()` requires the result page to pin the **target series** (branch/OS may be empty, the series may not); a target driver detail page alone remains sufficient | audit agent-b `low` (branch+os-only used to PASS) | `series-only-broad`, `no-series-filter`, `branch-os-only-insufficient`, `agent-b/verifier-probe/run-t9|t10_*` |
| T18 | The rubric-allowed "listing or search result" evidence is kept, but search evidence must contain a word token that actually appears in the article (purely numeric queries FAIL) | audit agent-c `low` plus rubric text | `news-search`, `news-search-numeric-only` |
| T19 | A new subscription row must, besides email, also have `topic` equal to this store's GeForce list value | audit agent-c `low` (`topic=NotTheGeForceTopic` used to PASS) | `wrong-topic`, `geforce-topic` |
