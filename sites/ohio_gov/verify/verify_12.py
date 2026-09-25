#!/usr/bin/env python3
"""Verify Ohio.gov--12.

Search "tax" chain: how many Resources results and how many FAQs results the
search reports; the Licenses tab's first result with its issuing agency; the
FAQs tab's first question (what its answer says you can do with the
Department of Taxation's online services); and one thing the Sales and Use
Tax resource says the tax applies to.

Frozen ground truth (tracked data snapshot): searching "tax" reports 24
Resources results and 6 FAQs results. The Licenses tab's first result is
"Vendor's License or Seller's Use Tax Account" issued by Taxation. The FAQs
tab's first question is "Can I file my state taxes online?" whose answer says
the Department of Taxation's online services let Ohioans file their
individual income tax returns, check their refund status, and make payments.
The Sales and Use Tax resource says Ohio levies the tax on the retail sale,
lease, and rental of personal property and the sale of selected services.
"""
from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_count, contains_phrase, final_answer,
                        navigated_with_query, run_verifier)

TASK_ID = "Ohio.gov--12"
SEARCH_PATH = "/search"
SALES_USE_TAX = "/business/resources/sales-and-use-tax"
TAXES_FAQ = "/help-center/faqs/taxes"


def _searched(traj, param, value):
    return (navigated_with_query(traj, SEARCH_PATH, "search_query", value)
            or navigated_with_query(traj, SEARCH_PATH, "q", value))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the search page for "tax" (Resources tab), the
    # Licenses tab, the FAQs tab, the first question's FAQ category page,
    # and the Sales and Use Tax resource page
    judge.check("searched_tax", _searched(traj, "search_query", "tax"),
                "required: /search?q=tax (Resources tab)")
    judge.check("switched_to_licenses_tab",
                navigated_with_query(traj, SEARCH_PATH, "t", "licenses"),
                "required: /search?q=tax&t=Licenses")
    judge.check("switched_to_faqs_tab",
                navigated_with_query(traj, SEARCH_PATH, "t", "faqs"),
                "required: /search?q=tax&t=FAQs")
    check_visited_path(judge, traj, "visited_first_faq_category", TAXES_FAQ)
    check_visited_path(judge, traj, "visited_sales_and_use_tax", SALES_USE_TAX)
    # answer: resources count, faqs count, first license + agency, online
    # services, applies-to
    judge.check("answer_resources_count", contains_count(answer, 24),
                "expected: 24 Resources results")
    judge.check("answer_faqs_count", contains_count(answer, 6),
                "expected: 6 FAQs results")
    judge.check("answer_first_license",
                contains_phrase(answer, "vendor's license"),
                "expected first license: Vendor's License or Seller's Use Tax Account")
    judge.check("answer_license_agency", contains_phrase(answer, "taxation"),
                "expected issuing agency: Taxation")
    judge.check("answer_online_services",
                contains_phrase(answer, "file") and (contains_phrase(answer, "refund")
                                                     or contains_phrase(answer, "payment")),
                "expected: the online services let you file individual income tax "
                "returns, check refund status, and make payments")
    judge.check("answer_applies_to",
                contains_phrase(answer, "retail sale")
                and contains_phrase(answer, "personal property"),
                "expected: the tax applies to the retail sale, lease, and rental of "
                "personal property and the sale of selected services")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
