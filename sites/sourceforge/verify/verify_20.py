#!/usr/bin/env python3
"""Verify SourceForge--20.

I'm evaluating ERP software and want an open source option. Browse the Business Software directory's ERP category and report every product listed with rating and ratings count. Open both products' business pages and report their descriptions. Then search the open source directory for "erp" sorted by Rating: report the result count, open the first result's project page and report its summary, license, weekly downloads, last update, and registered date, and open the second result's page and report its registered date. From the first result's Reviews page report the average rating and review count, and its Support tab's help recommendation.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--20"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_erp", r"/software/erp/")
    check_visited_path(judge, traj, "visited_odoo", r"/software/product/Odoo/")
    check_visited_path(judge, traj, "visited_dolibarr_biz", r"/software/product/Dolibarr/")
    check_visited_path(judge, traj, "erp_search_sorted", r"/directory/\?q=erp.*sort=rating")
    check_visited_path(judge, traj, "visited_dolibarr", r"/projects/dolibarr/")
    check_visited_path(judge, traj, "visited_dolibarr_reviews", r"/projects/dolibarr/reviews/")
    check_visited_path(judge, traj, "visited_dolibarr_support", r"/projects/dolibarr/support")
    check_visited_path(judge, traj, "visited_pseint", r"/projects/pseint/")
    check_answer_phrase(judge, answer, "product_odoo", 'Odoo')
    check_answer_phrase(judge, answer, "product_dolibarr", 'Dolibarr')
    check_answer_phrase(judge, answer, "odoo_rating", '4.3')
    check_answer_phrase(judge, answer, "odoo_ratings_count", '4,100')
    check_answer_phrase(judge, answer, "dolibarr_rating", '4.2')
    check_answer_phrase(judge, answer, "dolibarr_ratings_count", '940')
    check_answer_phrase(judge, answer, "odoo_description", 'suite of open source business apps')
    check_answer_phrase(judge, answer, "dolibarr_biz_description", 'Open source ERP and CRM web software for business')
    check_answer_number(judge, answer, "erp_results", 8, 'erp search result count')
    check_answer_phrase(judge, answer, "dolibarr_summary", 'Open source ERP and CRM web software for business')
    check_answer_phrase(judge, answer, "dolibarr_license", 'GPLv3')
    check_answer_number(judge, answer, "dolibarr_week", 2932, 'Dolibarr weekly downloads')
    check_answer_phrase(judge, answer, "dolibarr_updated", '2026-05-26')
    check_answer_phrase(judge, answer, "dolibarr_reg", '2005-11-28')
    check_answer_number(judge, answer, "dolibarr_rating_avg", '4.8', 'Dolibarr average rating')
    check_answer_number(judge, answer, "dolibarr_reviews", 52, 'Dolibarr review count')
    check_answer_phrase(judge, answer, "dolibarr_support_rec", 'discussion forums')
    check_answer_phrase(judge, answer, "pseint_reg", '2004-11-28')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
