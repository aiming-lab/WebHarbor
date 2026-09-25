# Medicare.gov deterministic grading

The 15 task entry points use `review_contract.py` for task-specific answer,
navigation and exact database-delta checks, and `verify_lib.py` for evidence
validation and the frozen seed contract. Run through the primary evaluator:

```sh
python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
python -m pytest sites/medicare_gov/verify/tests -q
```

Each run needs `trajectory.json`, referenced screenshots, `initial.db` and
`after.db`. The initial fixture must match the frozen schema/row hashes in
`verify_lib.py`. The reviewed changes do not change that schema or seed.

Read tasks preserve all database rows. Account tasks permit login events for
the requested account and only their requested changes: the designated message
read flag, Bob's due premium payment, Alice's move and lost-card request, or
publication orders. Anonymous publication orders now persist and are graded
against exact quantity, format, address, owner and status. Existing rows and
other users' data must remain unchanged. Task 7 accepts the claims list for
claim amounts; its related Summary Notice message establishes the service
period. Opening detail pages unnecessarily is not a grading requirement.

Answer checks bind entities to costs, dates, ratings and other requested facts;
they accept natural prose, bullets and labeled tables. The tests include
paraphrases, swapped values, unrelated reference numbers, contradictions,
wrong state, missing actions, collateral writes and corrupt evidence.
Deterministic pattern matching is intentionally bounded and is not a general
semantic judge. There is no mandatory answer template or minimum click count.

Task refinement emphasizes one coherent user goal and more than five meaningful
UI actions. Evidence counts exclude initial loading, final-answer submission,
waits and viewport diagnostics. The plan catalog is fictional benchmark data,
explicitly labeled in the UI; plan tasks assess the mirrored fixture, not real
insurance advice or a current commercial offer.
