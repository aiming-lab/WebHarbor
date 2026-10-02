# Amazon verifier contract

Run `python -m pytest sites/amazon/verify/test_verifiers.py sites/amazon/verify/test_subject_binding.py` from the repository root. For Amazon and ESPN, set `WH_CONTAINER` to a container built from this checkout to test against its real seed; fixture fallbacks are synthetic controls, not runtime validation.

The attribution helpers attach reported values to named subjects. Same-sentence
and same-row facts take precedence; nearby continuation prose remains accepted.
The controls cover natural sentences, tables, reversed value/name order,
swapped subjects, explicit negation, and numeric boundaries. Existing navigation,
run-package and database-state gates remain in force.

These deterministic rules use bounded text matching, not general semantic
understanding. Passing controls establish regression coverage, not acceptance of
every possible paraphrase or rejection of every contradiction. Test packages are
synthetic and must not be presented as browser trajectories. Grade real runs
through `agent_demo/eval_judge.py --run_dir RUN --verifier True`.
