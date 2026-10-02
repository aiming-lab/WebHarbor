# Reviewer grading for apartments_com

Run through the repository entrypoint:

```bash
uv run --project agent_demo python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
```

The run must carry the current task definition and verifier path, ordered browser actions with real URLs and decodable screenshots, a natural-language final answer, and immutable `initial.db` / `after.db` snapshots. The verifier never falls back to a running site database. Eventbrite calendar tasks also require the actual `event.ics` download.

`contract.json` contains reviewer-only expectations: frozen initial fixture fingerprints, required content pages, entity-scoped answer claims, and exact allowed state changes. Ground truth is intentionally absent from `tasks.jsonl`. Existing rows and unrelated fields must be preserved; only designated view counters may increase. New rows are checked for ownership, target, amount and content. Registration checks the password hash, and receipts must match the saved order or confirmation.

Answer matching uses finite language patterns. It accepts the documented prose, bullets, reordered rows and selected monetary equivalents, but does not claim unrestricted semantic understanding. The primary review includes real scripted browser runs, separate positive/negative grading controls, and manual comparison to rendered content. A passing grader alone does not establish visual quality or minimum task difficulty. No secondary LLM judge was used.

Review evidence and the dashboard are retained under `/data/webharbor-prs/final/pr239/`. The recordings are scripted browser regressions with reviewer-authored summaries, not independent agent discovery.

Specialty housing evidence may come from the complete student-housing page or
its filtered search. Counts bind to each city. The property comparison now explicitly distinguishes the overall advertised
range from the matching-available-unit range, using the property and search
surfaces to inform one rental choice. Ranges must match both property and meaning. Luxury-result tasks accept
the fully filtered/sorted results without an unnecessary detail-page visit.
