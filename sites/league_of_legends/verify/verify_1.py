#!/usr/bin/env python3
"""Verify League of Legends--1: Marksman role + Medium difficulty roster filter."""
from verify_lib import (check_read_only, check_trajectory_identity, champion_count_named,
                        contains_count, final_answer, navigated_champions_listing, run_verifier)

TASK_ID = "League of Legends--1"
# Frozen ground truth (seed DB, champions with roles containing "Marksman" and
# difficulty_name == "Medium"): 24 champions.
CHAMPIONS = ["Ashe", "Caitlyn", "Corki", "Ezreal", "Jayce", "Jhin", "Jinx",
             "Kai'Sa", "Kalista", "Kayle", "Kindred", "Kog'Maw", "Lucian", "Quinn",
             "Samira", "Senna", "Sivir", "Smolder", "Teemo", "Tristana", "Twitch",
             "Xayah", "Yunara", "Zeri"]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_champions_with_marksman_medium_filter",
                navigated_champions_listing(traj, {"role": "Marksman", "difficulty": "Medium"}),
                "required: /champions/?role=Marksman&difficulty=Medium")
    judge.check("answer_count", contains_count(answer, 24), "expected 24 champions")
    named = champion_count_named(answer, CHAMPIONS)
    judge.check("answer_names_all", named == len(CHAMPIONS),
                f"expected all {len(CHAMPIONS)} marksman names; matched {named}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
