#!/usr/bin/env python3
"""Verify UC Berkeley--12: the degree types the Haas School of Business offers.

The snapshot has exactly one Haas programme, contradicting the real-world
"MBA, PhD, …" prior. The negative check is clause-local: a degree type mentioned
in a clause with no Haas anchor (or in a negated clause) is not an offering.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_params_visited,
    check_read_only,
    check_trajectory_identity,
    contains_degree_type,
    contains_phrase,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    reconfirm_clause_split,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--12"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 12)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    programme = facts["programmes"][0]

    check_params_visited(
        judge, trajectory, "visited_haas_programme_listing", "/programs",
        {"college": facts["college"]["slug"]},
    )
    judge.check(
        "answer_has_programme",
        contains_phrase(answer, programme["name"]),
        f"expected_programme={programme['name']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_degree_type",
        contains_degree_type(answer, *facts["offered_types"]),
        f"expected_degree_types={facts['offered_types']!r}, answer={answer!r}",
    )
    claimed = sorted({
        other
        for clause in reconfirm_clause_split(answer)
        if re.search(r"\bhaas\b|business administration", clause)
        for other in facts["other_types"]
        if contains_degree_type(clause, other)
    })
    judge.check(
        "answer_no_other_haas_degrees",
        not claimed,
        f"catalogue_degree_types_not_offered_by_haas={facts['other_types']!r}, "
        f"claimed_near_haas={claimed!r}; answer={answer!r}",
    )
    check_read_only(judge, initial_db, after_db)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
