#!/usr/bin/env python3
"""Verify LandWatch--8 — Find an Agent directory.

Ground truth (frozen seed): the directory lists all 313 agents; the agent
with the most total listings is Mac A. Coalson of Coalson Real Estate.
"""

from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_count, contains_phrase,
                        final_answer, run_verifier)

TASK_ID = "LandWatch--8"
FIND_AGENT_PATH = "/find-agent"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_find_agent", FIND_AGENT_PATH)
    judge.check("answer_agent_count", contains_count(answer, 313),
                "expected 313 agents listed on the page")
    judge.check("answer_top_agent_name", contains_phrase(answer, "Mac A. Coalson"),
                "expected the top agent Mac A. Coalson")
    judge.check("answer_top_agent_brokerage", contains_phrase(answer, "Coalson Real Estate"),
                "expected the brokerage Coalson Real Estate")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
