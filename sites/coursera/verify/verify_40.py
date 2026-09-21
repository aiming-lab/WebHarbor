#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--40.

Browse Coursera for Business and Coursera for Teams and summarise some of their advantages.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Coursera for Business advantages: World-class content, Measurable outcomes, Recognized credentials, Curated content, Skill development, Mobile learning. Coursera for Teams advantages: Unlimited learning, Team analytics, Industry certificates, Collaborative learning, Any device, LMS integration.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
business + for-teams navigation | pages show the advantage sections | answer summarises >=2 advantages of each
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
    j, t, fa = load_task(a, "Coursera--40")
    j.check("nav_business", navigated_to(t, "/business"),
            "trajectory must open the Coursera for Business page")
    j.check("nav_teams", navigated_any(t, ["/for-teams", "/teams"]),
            "trajectory must open the Coursera for Teams page")
    biz_page = page_text_at(t, "/business")
    teams_page = page_text_at(t, "/for-teams") + "\n" + page_text_at(t, "/teams")
    j.check("page_shows_business_advantages", contains_all(biz_page, ["Why Coursera for Business?"]),
            "business page DOM must show the benefits section")
    j.check("page_shows_teams_advantages", contains_all(teams_page, ["Advantages of Coursera for Teams"]),
            "teams page DOM must show the advantages section")
    biz = [("World-class content", "world class content", "7,000+ courses",
           "300+ universities"),
          ("Measurable outcomes", "analytics", "measurable", "business-impact"),
          ("Recognized credentials", "credentials", "certificates"),
          ("Curated content", "curated", "learning paths"),
          ("Skill development", "skill gaps", "personalized"),
          ("Mobile learning", "mobile", "offline")]
    teams = [("Unlimited learning", "unlimited", "7,000+ courses", "course catalog"),
            ("Team analytics", "analytics dashboard", "analytics", "monitor"),
            ("Industry certificates", "certificates", "credentials"),
            ("Collaborative learning", "shared learning", "assign"),
            ("Any device", "across devices", "any device", "self-paced"),
            ("LMS integration", "LMS", "SSO", "integration")]
    n_biz = sum(1 for g in biz if any(contains_all(fa, [a]) for a in g))
    n_teams = sum(1 for g in teams if any(contains_all(fa, [a]) for a in g))
    j.check("answer_business_advantages", n_biz >= 2,
            f"business advantage groups matched={n_biz}/6 of {biz}")
    j.check("answer_teams_advantages", n_teams >= 2,
            f"teams advantage groups matched={n_teams}/6 of {teams}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
