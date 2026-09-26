#!/usr/bin/env python3
"""Verify SourceForge--6.

Our procurement team wants a CRM shortlist with an open source candidate. Browse the Business Software directory's CRM category and list every product with its rating and ratings count. Open each product's business page and report its full description and the category label it displays. Then search the open source directory for "CRM" sorted by Rating: report how many results it returns, open the first result's project page and report its summary, license, weekly downloads, and last update date, its average rating and review count from its Reviews page, and what its Support tab recommends for help.
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--6"



def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_crm", r"/software/crm/")
    check_visited_path(judge, traj, "visited_pipedrive", r"/software/product/Pipedrive/")
    check_visited_path(judge, traj, "visited_suitecrm", r"/software/product/SuiteCRM/")
    check_visited_path(judge, traj, "visited_espocrm", r"/software/product/EspoCRM/")
    check_visited_path(judge, traj, "crm_search_sorted", r"/directory/\?q=CRM.*sort=rating")
    check_visited_path(judge, traj, "visited_dolibarr", r"/projects/dolibarr/")
    check_visited_path(judge, traj, "visited_dolibarr_reviews", r"/projects/dolibarr/reviews/")
    check_visited_path(judge, traj, "visited_dolibarr_support", r"/projects/dolibarr/support")
    check_answer_phrase(judge, answer, "product_pipedrive", 'Pipedrive')
    check_answer_phrase(judge, answer, "product_suitecrm", 'SuiteCRM')
    check_answer_phrase(judge, answer, "product_espocrm", 'EspoCRM')
    check_answer_phrase(judge, answer, "pipedrive_ratings", '3,120')
    check_answer_phrase(judge, answer, "pipedrive_rating_value", '4.4')
    check_answer_phrase(judge, answer, "suitecrm_ratings", '1,150')
    check_answer_phrase(judge, answer, "espocrm_ratings", '480')
    check_answer_phrase(judge, answer, "pipedrive_description", 'easy-to-use CRM built for sales teams')
    check_answer_phrase(judge, answer, "category_label", 'CRM')
    check_answer_number(judge, answer, "crm_results", 2, 'CRM search result count')
    check_answer_phrase(judge, answer, "dolibarr_summary", 'Open source ERP and CRM web software for business')
    check_answer_phrase(judge, answer, "dolibarr_license", 'GPLv3')
    check_answer_number(judge, answer, "dolibarr_week", 2932, 'Dolibarr weekly downloads')
    check_answer_phrase(judge, answer, "dolibarr_updated", '2026-05-26')
    check_answer_number(judge, answer, "dolibarr_rating", '4.8', 'Dolibarr rating')
    check_answer_number(judge, answer, "dolibarr_reviews", 52, 'Dolibarr review count')
    check_answer_phrase(judge, answer, "dolibarr_support_rec", 'discussion forums')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
