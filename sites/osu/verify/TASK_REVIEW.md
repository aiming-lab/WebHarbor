# osu — task reasonableness review

Reviewer assessment of the 20 tasks in `sites/osu/tasks.jsonl` (from PR
[aiming-lab/WebHarbor#12](https://github.com/aiming-lab/WebHarbor/pull/12), which had
no prior review). Scope: are the tasks **feasible** (solvable by navigating the site),
**not trivially answerable from an LLM's prior knowledge**, and do they have a **stable
on-site answer**? Plus site-quality issues found while writing the grading contract.

## Method

1. Stood the site up locally (throwaway venv, no HF assets — osu builds its DB from
   `seed_data.py` at boot) and `curl`ed the page behind every task to confirm the answer
   is on-site and reachable, and to capture the exact rendered string.
2. Extracted the frozen ground truth from `seed_data.py` and hardcoded it into
   `verify_0.py … verify_19.py`.
3. Ran `selfcheck.py`: **20/20 tasks pass all three assertions** (a correct trajectory
   PASSes; a wrong answer FAILs; a right answer with no page visit FAILs).

## Verdict

**All 20 tasks are feasible, on-site answerable, stable, and now gradeable** (verifier +
rubric added). None are human-in-the-loop; none have an unstable on-site answer. Six are
weak (answerable from prior knowledge — mitigated, not fixed, by the navigation
anti-shortcut check) and one has an internal inconsistency. Per the reviewer/contributor
split these are **flagged, not rewritten** (the answers still come from the site).

## Per-task table

| # | Question (short) | On-site page | Ground truth (site) | Answerable from memory? |
|---|---|---|---|---|
| 0 | Fisher dean | `/academics` | Anil Makhija | No — site-specific |
| 1 | # varsity sports | `/about` | **36** | Partly (real ≈ same) — ⚠ see F2 |
| 2 | Athletics conference | `/athletics` | Big Ten | **Yes** (real-world true) |
| 3 | Football head coach | `/athletics/…-football` | Ryan Day | **Yes** (currently real) |
| 4 | Research expenditure | news article / `/about` | $1.3 billion | No — site-specific figure |
| 5 | Founding year | `/about` | 1870 | **Yes** (real-world true) |
| 6 | TDAI research focus | `/research/…-tdai` | data analytics, ML, health informatics, social science | No |
| 7 | Undergrad enrollment | `/about` | 46,820 | Partly (approx real) |
| 8 | List three colleges | `/academics` | any 3 of 16 seeded | **Yes** (generic) |
| 9 | Engineering degree types | `/programs?college=engineering` | BS, MS, PhD | Partly |
| 10 | Wrestling home venue | `/athletics/…-wrestling` | Covelli Center | No — site-specific |
| 11 | OSC director | `/research/ohio-supercomputer-center` | David Bickel | No — site-specific |
| 12 | Moritz professional degree | `/academics` / `/programs/juris-doctor-jd` | JD (Juris Doctor) | **Yes** (obvious) |
| 13 | Math dept chair | `/departments/department-of-mathematics` | James Cogdell | No — site-specific |
| 14 | Football home stadium | `/athletics/…-football` | Ohio Stadium (Horseshoe) | **Yes** (real-world true) |
| 15 | Wrestling nat'l titles | `/athletics/…-wrestling` | 8 | No — site-specific figure |
| 16 | MBA application deadline | `/programs/…-mba` | April 1 | No — site-specific |
| 17 | Cancer-breakthrough news | `/news/…-cancer-immunotherapy` | the CAR-T article | No — site-specific |
| 18 | James Cancer director | `/research/james-cancer…` | William Farrar | No — site-specific |
| 19 | Clean Hydrogen focus | `/research/center-for-clean-hydrogen` | hydrogen energy, fuel cells, green hydrogen, energy storage | No |

## Findings

### F1 — Knowledge-shortcut tasks (severity: minor; mitigated)
T2, T3, T5, T8, T12, T14 are answerable from an LLM's prior knowledge (Big Ten; Ryan Day;
1870; "name any 3 colleges"; JD; Ohio Stadium). The **navigation anti-shortcut check** in
each verifier requires the agent to actually open the relevant page, so a memory-only
answer FAILs even when correct — but these tasks test navigation more than retrieval.
Recommendation (optional): make them site-specific by asking for a co-located
non-guessable detail (e.g. the football coach's *recent record 11-2*, the wrestling
team's *venue*, a specific college's *dean*). Left as-is per the reviewer/contributor
split.

### F2 — Task 1 internal inconsistency (severity: major; flagged)
`/about` **states 36 varsity sports**, but only **27** teams are seeded (`/athletics`), so an
agent that counts teams answers 27. The verifier anchors to the authoritative stated
figure (36) and the rubric tells the judge to grade against 36. Recommendation for the
contributor: either seed 36 teams or reword to "How many varsity sports does the About
page state?".

### F3 — No frozen seed DB / images in git or HF (severity: info)
Unlike every other site, osu ships **no `instance_seed/osu.db`** and **no `static/images/`**;
its DB is generated from `seed_data.py` at **image-build time** (the `RUN` step added to the
`Dockerfile`). Upside: fully hermetic, no ~2.8 GB HF pull to reproduce/verify. Caveats:
(a) determinism now rests entirely on `seed_data.py`, and the benchmark-user rows use
`created_at=datetime.utcnow` → the generated `.db` is **not byte-reproducible across
builds** (stable within one image; the `/reset` byte-identity invariant still holds because
reset copies the build-frozen file); (b) no images → lower visual fidelity (fine for these
text-lookup tasks).

### F4 — `news_article` commits on GET (severity: minor)
`app.py` does `view_count += 1; db.session.commit()` on every `/news/<slug>` view, so the
live `instance/` DB drifts from `instance_seed/` as soon as any article is opened. It does
**not** break the post-`/reset` byte-identity check (which is measured right after the
restore copy), but it is an impurity worth noting.

### F5 — Dead code: `sites/osu/_health.py` (severity: trivial)
`_health.py` defines `health_check(...)` that nothing imports; `app.py` has its own inline
`/_health` route. Harmless; can be removed.

### F6 — Integration with current main (severity: was a blocker; **handled in this PR**)
PR #12 was cut from a stale base: its `websyn_start.sh` would have **dropped `booking` and
replaced `merriam_webster`**, and it claimed port **40015**, which current main assigns to
`merriam_webster`. This branch instead **adds osu as the 17th site on port 40016** (updating
`websyn_start.sh`, `control_server.py`, the `Dockerfile` `EXPOSE`/seed step, `tasks.jsonl`'s
`web` URL, and the site-count references), so it merges cleanly onto the current main with
no collision or regression.
