#!/usr/bin/env python3
"""Verify OhioMeansJobs--13.

Compare the Welder /Fitter II job at Daifuku America Corporation with the
Welder L1 job at Steele Solutions: report each one's city, posted date,
salary range and education level from its job summary, and state which lists
the higher salary range; also find the welder job in Huber Heights and report
its employer, posted date, education level, and the job types it offers.

Frozen ground truth (seed DB): Daifuku 'Welder /Fitter II' (6930719611) —
Reynoldsburg, OH, posted 2026-09-22, High Income Jobs ($80K-$99K), education
'High school diploma or equivalent'; Steele Solutions 'Welder L1'
(6931551306) — Tiffin, OH, posted 2026-09-23, Upper Middle Income Jobs
($50K-$79K), education 'High school diploma or equivalent'; Daifuku lists
the higher range. The Huber Heights welder is 'Welder' (6931641374) @ Enjet
Aero, posted 2026-09-23, education 'Postsecondary nondegree award', job
types Full-Time + Permanent. Read-only task.
"""
from verify_lib import (Judge, check_read_only, check_trajectory_identity,
                        contains_date, contains_phrase, final_answer,
                        navigated_job_detail, navigated_jobs_search,
                        run_verifier)

TASK_ID = "OhioMeansJobs--13"
DAIFUKU_ID = "6930719611"
STEELE_ID = "6931551306"
HUBER_ID = "6931641374"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_welder_search",
                navigated_jobs_search(traj, tjt=["welder"]),
                "required: /jobs/search with tjt=welder")
    judge.check("visited_daifuku_detail", navigated_job_detail(traj, DAIFUKU_ID),
                f"required: /jobs/view/{DAIFUKU_ID} (Welder /Fitter II at Daifuku)")
    judge.check("visited_steele_detail", navigated_job_detail(traj, STEELE_ID),
                f"required: /jobs/view/{STEELE_ID} (Welder L1 at Steele Solutions)")
    judge.check("visited_huber_detail", navigated_job_detail(traj, HUBER_ID),
                f"required: /jobs/view/{HUBER_ID} (the Huber Heights welder)")
    # answer facts
    judge.check("answer_daifuku_city", contains_phrase(answer, "Reynoldsburg"),
                "expected Daifuku city Reynoldsburg, OH")
    judge.check("answer_daifuku_posted", contains_date(answer, "2026-09-22"),
                "expected Daifuku posted 2026-09-22")
    judge.check("answer_daifuku_salary",
                contains_phrase(answer, "$80K-$99K") or contains_phrase(answer, "80k-99k"),
                "expected Daifuku High Income Jobs ($80K-$99K)")
    judge.check("answer_daifuku_education",
                contains_phrase(answer, "High school diploma"),
                "expected Daifuku education High school diploma or equivalent")
    judge.check("answer_steele_city", contains_phrase(answer, "Tiffin"),
                "expected Steele city Tiffin, OH")
    judge.check("answer_steele_posted", contains_date(answer, "2026-09-23"),
                "expected Steele posted 2026-09-23")
    judge.check("answer_steele_salary",
                contains_phrase(answer, "$50K-$79K") or contains_phrase(answer, "50k-79k"),
                "expected Steele Upper Middle Income Jobs ($50K-$79K)")
    judge.check("answer_steele_education",
                contains_phrase(answer, "High school diploma"),
                "expected Steele education High school diploma or equivalent")
    judge.check("answer_higher_daifuku", contains_phrase(answer, "Daifuku"),
                "expected Daifuku to be named as listing the higher salary range")
    judge.check("answer_huber_employer", contains_phrase(answer, "Enjet Aero"),
                "expected the Huber Heights welder employer Enjet Aero")
    judge.check("answer_huber_posted", contains_date(answer, "2026-09-23"),
                "expected the Huber Heights welder posted 2026-09-23")
    judge.check("answer_huber_education",
                contains_phrase(answer, "Postsecondary nondegree"),
                "expected the Huber Heights welder education Postsecondary nondegree award")
    judge.check("answer_huber_types",
                contains_phrase(answer, "Full-Time") and contains_phrase(answer, "Permanent"),
                "expected the Huber Heights welder job types Full-Time + Permanent")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
