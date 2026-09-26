#!/usr/bin/env python3
"""verify_5.py — deterministic verifier for task REMAX--5.

Spanish-speaking agent profile (name, office city, years, hobby, license
number) plus the 30-or-more-years cohort (count and most experienced agent).

Ground truth below is HARDCODED (frozen against the shipped seed DB); it never
appears in tasks.jsonl. Navigation gates encode the honest on-site path the
task text implies; a correct answer without that navigation is a shortcut and
fails. See verify_lib.py for the shared contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_lib import (  # noqa: E402
    Judge, check_read_only, check_trajectory_identity, contains_any_phrase,
    contains_count, contains_phrase, final_answer, nav_agent_detail,
    nav_agents_filtered, run_verifier)

TASK_ID = "REMAX--5"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: agent finder filtered to Spanish + Wesley's profile;
    # the 30+ cohort must come from the directory (filtered or read)
    judge.check("nav_agents_spanish",
                nav_agents_filtered(traj, language="Spanish"),
                "required: /real-estate-agents with language=Spanish")
    judge.check("nav_agent_wesley", nav_agent_detail(traj, "100016948"),
                "required: agent detail for Wesley Hardin (100016948)")
    judge.check("nav_agents_30y_cohort",
                nav_agents_filtered(traj, years="30"),
                "required: /real-estate-agents with years=30")
    judge.check("nav_agent_ivy", nav_agent_detail(traj, "100000955"),
                "required: agent detail for Ivy Boland (100000955)")
    # ground truth (frozen seed): Wesley Hardin, office in Aurora, 28 years,
    # hobbies include Sports, license FA40014061; 7 agents have 30+ years;
    # the most experienced is Ivy Boland with 50 years
    judge.check("answer_name", contains_phrase(answer, "Wesley Hardin"),
                "must name Wesley Hardin")
    judge.check("answer_office_city", contains_phrase(answer, "Aurora"),
                "must state the office city Aurora")
    judge.check("answer_years", contains_count(answer, 28),
                "must state 28 years of experience")
    judge.check("answer_hobby", contains_phrase(answer, "Sports"),
                "must name the Sports hobby")
    judge.check("answer_license", contains_phrase(answer, "FA40014061"),
                "must quote license number FA40014061")
    judge.check("answer_cohort_count", contains_count(answer, 7),
                "must state 7 agents have 30+ years of experience")
    judge.check("answer_most_experienced", contains_phrase(answer, "Ivy Boland"),
                "must name Ivy Boland as the most experienced")
    judge.check("answer_most_experienced_years", contains_count(answer, 50),
                "must state Ivy Boland's 50 years")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
