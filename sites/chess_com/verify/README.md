# chess_com deterministic task verification

Run each task through the visible UI from a fresh site state. Save `trajectory.json`, decodable before/after PNG screenshots, `initial.db` and `after.db`. Grade with:

```bash
python agent_demo/eval_judge.py --run_dir /path/to/run --verifier True
```

The verifier checks task identity, local origin, required content visits, requested facts and database outcomes. The initial snapshot must match the frozen seed. Research tasks preserve all rows; stateful tasks permit only the requested changes. Natural prose, bullets and tables are accepted within the deterministic parser's documented patterns. These checks do not provide unrestricted natural-language understanding.

Research expectations are in `refined_contract.json`. Task 25 requires one successful, unhinted attempt on puzzle 1 for david_k; unchanged attempts are preserved.

Tests use portable local seed fixtures and separately labelled synthetic evidence. Build the seed with `seed_data.py` before running site and verifier tests.

The reviewed seed also removes captured navigation/board-coordinate residue from
opening descriptions and HTML markup from club descriptions, and corrects the
Slav Defense move summary from its captured Starting Position paragraph. The
logical seed fingerprint includes these changes. Run renderer regressions with
`node --test sites/chess_com/tests/test_board.js` from the repository root.
