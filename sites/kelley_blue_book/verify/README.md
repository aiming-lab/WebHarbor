# Reviewer grading contract

Run `python agent_demo/eval_judge.py --run_dir RUN --verifier True` from the repository root. The trajectory must carry the current task ID/text and reviewer verifier path, completion status, ordered UI actions and screenshot references. Save `initial.db` and `after.db` in the run directory using SQLite backup; the grader never falls back to a mutable live database.

The primary grader verifies the reviewed initial fixture, relevant page evidence, entity-bound factual claims and exact requested state deltas. It preserves unrelated rows, ownership, quantities, variants and history. Review aggregates retain the upstream total (the archived review text is only a sample). Efficient correct paths pass; action counts describe recorded review paths only and are not grading criteria.

Natural sentences, bullets and tables are accepted within the documented lexical patterns. This deterministic matcher has bounded paraphrase coverage; it is not a general semantic judge or proof of screenshot authenticity. Prices require currency, ratings use stars/rating language, and quantities identify their entity. Ground truth remains in reviewer-only contracts, never the agent-facing task prompts. Scripted review reference answers are not independent agent performance. The secondary LLM judge was not run.
