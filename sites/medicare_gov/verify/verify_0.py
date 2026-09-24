#!/usr/bin/env python3
"""Verify Medicare.gov--0 — three-condition coverage check (acupuncture, glaucoma,
shingles) for a 68-year-old father with chronic low back pain, diabetes, and a
family history of glaucoma.

Read-only task. Ground truth (frozen seed, all facts on the coverage detail
pages): acupuncture for chronic low back pain is covered up to 12 treatments in
90 days (additional 8 if improving, maximum 20 in a 12-month period), chronic
means lasting 12 weeks or longer; high-risk glaucoma screening once every 12
months; shingles vaccine costs $0 with Part D (ACIP-recommended adult vaccines).
"""

from verify_lib import (Judge, advisory_llm_answer, check_read_only,
                        check_trajectory_identity, contains_count,
                        contains_money, contains_phrase, final_answer,
                        navigated_to_path, run_verifier)

TASK_ID = "Medicare.gov--0"
GROUND_TRUTH = ("Acupuncture for chronic low back pain: up to 12 treatments in 90 days; "
                "an additional 8 sessions if improving for a maximum of 20 treatments in a "
                "12-month period; chronic means the pain has lasted 12 weeks or longer. "
                "Glaucoma screening for someone at high risk: once every 12 months. "
                "Shingles vaccine with Part D: you pay nothing ($0); Part D covers all "
                "ACIP-recommended adult vaccines.")
QUESTION = ("For a 68-year-old with chronic low back pain, diabetes, and a family history "
            "of glaucoma: how many acupuncture treatments per 90 days and what maximum in a "
            "12-month period (and how long must the pain have lasted to count as chronic), "
            "how often can someone at high risk get a glaucoma screening, and what would he "
            "pay for the shingles vaccine with Part D?")

COVERAGE_BROWSE = ("/coverage/search", "/coverage/popular-topics", "/coverage/find-alphabetically")


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the three coverage detail pages (the only place the facts exist)
    judge.check("opened_acupuncture_detail",
                navigated_to_path(traj, "/coverage/acupuncture"),
                "required_path=/coverage/acupuncture")
    judge.check("opened_glaucoma_screenings_detail",
                navigated_to_path(traj, "/coverage/glaucoma-screenings"),
                "required_path=/coverage/glaucoma-screenings")
    judge.check("opened_shingles_vaccines_detail",
                navigated_to_path(traj, "/coverage/shingles-vaccines"),
                "required_path=/coverage/shingles-vaccines")
    # ... plus real use of the coverage database (search or browse), not URL guessing
    judge.check("used_coverage_database",
                any(navigated_to_path(traj, p) for p in COVERAGE_BROWSE),
                f"any_of={COVERAGE_BROWSE}")
    # answer gates
    judge.check("answer_12_treatments_per_90_days",
                contains_count(answer, 12) and contains_phrase(answer, "90 days"),
                "expected 12 treatments per 90 days")
    judge.check("answer_max_20_in_12_month",
                contains_count(answer, 20) and
                (contains_phrase(answer, "12-month") or contains_phrase(answer, "12 month")
                 or contains_phrase(answer, "12 months")),
                "expected the maximum of 20 treatments in a 12-month period")
    judge.check("answer_chronic_12_weeks",
                contains_phrase(answer, "12 weeks"),
                "expected chronic = lasting 12 weeks or longer")
    judge.check("answer_glaucoma_every_12_months",
                contains_phrase(answer, "every 12 months"),
                "expected once every 12 months for high risk")
    judge.check("answer_shingles_0_with_part_d",
                (contains_money(answer, 0) or contains_phrase(answer, "nothing")
                 or contains_phrase(answer, "no cost") or contains_phrase(answer, "free"))
                and contains_phrase(answer, "part d"),
                "expected $0 / pay nothing with Part D")
    check_read_only(judge, initial_db, after_db)
    advisory_llm_answer(judge, answer, GROUND_TRUTH, QUESTION)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
