#!/usr/bin/env python3
"""Verify SourceForge--20.

I'm evaluating ERP software and want an open source option. Browse the Business Software directory's ERP category and report every product listed with its rating and ratings count. Then identify which product also exists in the open source directory, open its project page, and report its summary, license, weekly downloads, and last update date.
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
    check_visited_path(judge, traj, "visited_dolibarr", r"/software/product/Dolibarr")
    check_visited_path(judge, traj, "visited_dolibarr_project", r"/projects/dolibarr/")
    check_answer_phrase(judge, answer, "product_odoo", 'Odoo')
    check_answer_phrase(judge, answer, "product_dolibarr", 'Dolibarr')
    check_answer_phrase(judge, answer, "odoo_rating", '4.3')
    check_answer_phrase(judge, answer, "odoo_ratings_count", '4,100')
    check_answer_phrase(judge, answer, "dolibarr_rating", '4.2')
    check_answer_phrase(judge, answer, "dolibarr_ratings_count", '940')
    check_answer_phrase(judge, answer, "dolibarr_summary", 'Open source ERP and CRM web software for business')
    check_answer_number(judge, answer, "dolibarr_week", 2932, 'Dolibarr weekly downloads')
    check_answer_phrase(judge, answer, "dolibarr_updated", '2026-05-26')
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
