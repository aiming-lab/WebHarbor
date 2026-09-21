#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--39.

Find the Space Safety course offered by TUM; how many videos are in module 2 and what is the name of each video?

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): 'Space Safety' (Technical University of Munich) module 2 'Space Debris' contains 7 videos: Where Space Debris Comes From / The Kessler Syndrome Explained / Tracking Debris from the Ground / On-Orbit Conjunction Assessment / Active Debris Removal Concepts / Post-Mission Disposal Guidelines / Future Outlook for Orbital Sustainability.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the module videos | answer states 7 videos + >=6 of the 7 video titles
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (parse_args, load_task, check_read_only, grade_options,
                        course_option_ok, search_card_ok,
                        navigated_to, navigated_any, navigated_to_course, query_has, page_text_at,
                        contains_all, contains_any, counts, has_number, numbers_in,
                        pct_of, star_level_lowest, re_found, fold, is_mirror_url,
                        states_no_other_courses,
                        step_urls, _url_path)


def main():
    a = parse_args()
    j, t, fa = load_task(a, "Coursera--39")
    page = page_text_at(t, "/learn/space-safety")
    j.check("nav_course", navigated_to_course(t, "space-safety"),
            "trajectory must open the Space Safety page")
    vids = ["Where Space Debris Comes From", "The Kessler Syndrome Explained",
            "Tracking Debris from the Ground", "On-Orbit Conjunction Assessment",
            "Active Debris Removal Concepts", "Post-Mission Disposal Guidelines",
            "Future Outlook for Orbital Sustainability"]
    j.check("page_shows_module_videos", contains_all(page, ["Space Safety", "Space Debris",
                                                          "The Kessler Syndrome Explained"]),
            "observed DOM must show the module 2 videos")
    j.check("answer_video_count", counts(fa, 7, "video", "videos"),
            "answer must state that module 2 has 7 videos")
    found = [v for v in vids if contains_all(fa, [v])]
    j.check("answer_names_videos", len(found) >= 6,
            f"video titles found={len(found)}/7; missing={[v for v in vids if v not in found]}")
    j.check("answer_references_module2", contains_any(fa, ["Space Debris", "module 2"]),
            "answer must reference module 2 / the Space Debris module")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
