#!/usr/bin/env python3
"""verify_7.py — deterministic verifier for task REMAX--7.

Grapevine office found via the office finder's Hindi filter (each matching
office page checked for service areas): office name, website, two non-English
languages, another service area, how many of the matching offices serve
Dallas, and how many offices the site search finds for Grapevine.

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
    contains_count, contains_phrase, final_answer, nav_office_detail,
    nav_offices_filtered, nav_search_query, run_verifier)

TASK_ID = "REMAX--7"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # anti-shortcut: the Hindi-filtered office finder, the pages of the five
    # matching offices, and the site search for Grapevine
    judge.check("nav_offices_hindi",
                nav_offices_filtered(traj, language="Hindi"),
                "required: /real-estate-offices with language=Hindi")
    for rid, name in (("2000100427347", "REMAX 2000"),
                      ("100427517", "REMAX City Square"),
                      ("100424335", "REMAX DFW Associates I"),
                      ("100429718", "REMAX Direct"),
                      ("100427352", "REMAX Frontier")):
        judge.check(f"nav_office_{rid}", nav_office_detail(traj, rid),
                    f"required: office detail for {name} ({rid})")
    judge.check("nav_search_grapevine",
                nav_search_query(traj, ["grapevine"]),
                "required: site search for Grapevine")
    # ground truth (frozen seed): REMAX DFW Associates I (Coppell TX),
    # website www.yourhometownpro.com, staff languages besides English
    # include Hindi/Spanish/Urdu/Punjabi/Gujarati/Mandarin/Sign Language,
    # other service areas include Flower Mound/Southlake/Colleyville/
    # Lewisville/Dallas/Irving; 1 of the 5 Hindi offices serves Dallas;
    # the site search finds 1 office for Grapevine
    judge.check("answer_office_name",
                contains_any_phrase(answer, ["DFW Associates", "Dfw Associates I"]),
                "must name REMAX DFW Associates I")
    judge.check("answer_website",
                contains_any_phrase(answer, ["yourhometownpro.com",
                                             "www.yourhometownpro.com"]),
                "must quote the office website www.yourhometownpro.com")
    langs = [p for p in ("Hindi", "Spanish", "Urdu", "Punjabi", "Gujarati",
                         "Mandarin", "Sign Language") if contains_phrase(answer, p)]
    judge.check("answer_two_languages", len(set(langs)) >= 2,
                f"must name two non-English staff languages, saw: {langs}")
    areas = [p for p in ("Flower Mound", "Southlake", "Colleyville", "Lewisville",
                         "Dallas", "Irving") if contains_phrase(answer, p)]
    judge.check("answer_another_area", len(areas) >= 1,
                f"must name another service area, saw: {areas}")
    judge.check("answer_dallas_serving_count", contains_count(answer, 1),
                "must state 1 of the matching offices serves Dallas")
    judge.check("answer_search_office_count", contains_count(answer, 1),
                "must state the site search finds 1 office for Grapevine")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
