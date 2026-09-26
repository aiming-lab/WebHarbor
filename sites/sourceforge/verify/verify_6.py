#!/usr/bin/env python3
"""Verify SourceForge--6.

Our procurement team wants a CRM shortlist. Browse the Business Software directory's CRM category, list the products shown, and report which one has the most ratings and its rating value. Then open that product's page and give its full description, plus the category label the page displays.
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
    check_answer_phrase(judge, answer, "product_pipedrive", 'Pipedrive')
    check_answer_phrase(judge, answer, "product_suitecrm", 'SuiteCRM')
    check_answer_phrase(judge, answer, "product_espocrm", 'EspoCRM')
    check_answer_phrase(judge, answer, "most_ratings_count", '3,120')
    check_answer_phrase(judge, answer, "most_ratings_value", '4.4')
    check_answer_phrase(judge, answer, "pipedrive_description", 'easy-to-use CRM built for sales teams')
    check_answer_phrase(judge, answer, "category_label", 'CRM')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
