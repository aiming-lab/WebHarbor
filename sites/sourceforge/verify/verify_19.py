#!/usr/bin/env python3
"""Verify SourceForge--19.

What does SourceForge offer beyond project downloads? Report: the About page's founding year and software title count; the first two Team members' names and titles; the newest episode's and article's titles and dates from the Podcast and Articles pages; the Case Studies featured vendors, plus the ratings counts on the NinjaOne and Google Cloud Platform product pages; the newest Blog post's title and date; what the For Vendors page offers; the Create page's invitation; the Support page's fastest way to get help; the footer's headquarters street address; and how many projects a directory search for 'file compression' returns.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--19"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_about", r"/about")
    check_visited_path(judge, traj, "visited_leadership", r"/about/leadership")
    check_visited_path(judge, traj, "visited_podcast", r"/podcast/")
    check_visited_path(judge, traj, "visited_articles", r"/articles/")
    check_visited_path(judge, traj, "visited_case_studies", r"/software/case-studies/")
    check_visited_path(judge, traj, "visited_ninjaone", r"/software/product/NinjaOne/")
    check_visited_path(judge, traj, "visited_gcp", r"/software/product/Google-Cloud-Platform/")
    check_visited_path(judge, traj, "visited_blog", r"/blog/")
    check_visited_path(judge, traj, "visited_vendors", r"/software/vendors/")
    check_visited_path(judge, traj, "visited_create", r"/create")
    check_visited_path(judge, traj, "visited_support", r"/support")
    check_visited_path(judge, traj, "visited_file_compression_search", r"/directory/.*file.compression")
    check_answer_phrase(judge, answer, "founded_1999", '1999')
    check_answer_phrase(judge, answer, "software_titles", '123,200')
    check_answer_phrase(judge, answer, "leader_1", 'Logan Abbott')
    check_answer_phrase(judge, answer, "leader_1_title", 'President, SourceForge')
    check_answer_phrase(judge, answer, "leader_2", 'Roger Sheppard')
    check_answer_phrase(judge, answer, "leader_2_title", 'President of Slashdot Media')
    check_answer_phrase(judge, answer, "podcast_episode", 'FastField')
    check_answer_phrase(judge, answer, "podcast_episode_number", '#138')
    check_answer_phrase(judge, answer, "podcast_date", '2026-09-03')
    check_answer_phrase(judge, answer, "newest_article", 'Trend Analysis and Capacity Planning')
    check_answer_phrase(judge, answer, "article_date", '2026-09-03')
    check_answer_phrase(judge, answer, "vendor_1", 'Gemini Enterprise Agent Platform')
    check_answer_phrase(judge, answer, "vendor_2", 'Google Cloud Platform')
    check_answer_phrase(judge, answer, "vendor_3", 'NinjaOne')
    check_answer_number(judge, answer, "ninjaone_ratings", '6,035', 'NinjaOne ratings count')
    check_answer_number(judge, answer, "gcp_ratings", '61,049', 'Google Cloud Platform ratings count')
    check_answer_phrase(judge, answer, "newest_blog_post", 'Trend Analysis and Capacity Planning')
    check_answer_phrase(judge, answer, "blog_date", '2026-09-03')
    check_answer_phrase(judge, answer, "vendors_offer", 'list your product in the Business Software directory')
    check_answer_phrase(judge, answer, "create_invite", 'Find, Create & Publish Open Source software for free')
    check_answer_phrase(judge, answer, "support_fastest", 'fastest way to get help')
    check_answer_phrase(judge, answer, "hq_address", '1320 Columbia Street Suite 310')
    check_answer_phrase(judge, answer, "hq_city", 'San Diego')
    check_answer_number(judge, answer, "file_compression_count", 96, "projects returned by the 'file compression' directory search")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
