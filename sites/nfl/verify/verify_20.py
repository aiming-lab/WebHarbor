#!/usr/bin/env python3
"""Verify NFL--20.

Sign up gameday.fan@example.com for the NFL newsletter using the footer form
(Chiefs), confirm the site's confirmation message, then sign up
tailgate.buddy@example.com with the Miami Dolphins. Finally, report the
combined record of the Chiefs' next two opponents this season, each opponent's
head coach and home stadium, and each of those two games' day, kickoff and
stadium from the game centers.

Frozen ground truth (seed DB): the footer form posts to /newsletter/ and the
page confirms with "You're signed up for the NFL newsletter." The Chiefs' next
two scheduled games are Week 3 at the Miami Dolphins (0-2; Jeff Hafley; Hard
Rock Stadium; SUN 1:00pm ET) and Week 4 at the Las Vegas Raiders (2-0; Klint
Kubiak; Allegiant Stadium; SUN 4:25pm ET) — combined record 2-2. DB delta:
exactly two newsletter_signups rows (gameday.fan@example.com -> KC,
tailgate.buddy@example.com -> MIA); nothing else changes.
"""
from verify_lib import (Judge, check_only_tables_changed, check_precise_delta,
                        check_trajectory_identity,
                        contains_phrase, contains_record, contains_time, entered_identity,
                        final_answer, navigated_to, newsletter_rows, run_verifier)

TASK_ID = "NFL--20"
EMAIL_1 = "gameday.fan@example.com"
TEAM_1 = "KC"
EMAIL_2 = "tailgate.buddy@example.com"
TEAM_2 = "MIA"
OPPONENTS = (
    ("Dolphins", (0, 2), "Jeff Hafley", "Hard Rock Stadium", "13:00"),
    ("Raiders", (2, 0), "Klint Kubiak", "Allegiant Stadium", "16:25"),
)
COMBINED = (2, 2)


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: the footer form (homepage), the Chiefs schedule, both
    # game centers, and both opponents' team pages
    judge.check("visited_home_footer_form", navigated_to(traj, "/"),
                "required: / (footer newsletter form)")
    judge.check("typed_both_emails",
                entered_identity(traj, EMAIL_1) and entered_identity(traj, EMAIL_2),
                f"required: both emails {EMAIL_1} and {EMAIL_2} typed into the form")
    judge.check("visited_chiefs_schedule",
                navigated_to(traj, "/teams/kansas-city-chiefs/schedule"),
                "required: the Chiefs schedule (next two opponents)")
    judge.check("visited_game_centers",
                navigated_to(traj, "chiefs-at-dolphins-2026-reg-3")
                and navigated_to(traj, "chiefs-at-raiders-2026-reg-4"),
                "required: both next-game game centers")
    judge.check("visited_opponent_team_pages",
                navigated_to(traj, "/teams/miami-dolphins")
                and navigated_to(traj, "/teams/las-vegas-raiders"),
                "required: both opponents' team pages (coaches + stadiums)")
    # answer gates: confirmation + both opponents with coaches/stadiums + combined
    judge.check("answer_confirms_signup",
                any(p in answer.lower() for p in
                    ("signed up", "signup worked", "confirmed", "you're signed up",
                     "newsletter signup")),
                "the answer must confirm the newsletter signups worked")
    for name, (w, l), coach, stadium, kickoff in OPPONENTS:
        judge.check(f"answer_opponent_{name.lower()}",
                    contains_phrase(answer, name) and contains_record(answer, w, l),
                    f"expected {name} ({w}-{l})")
        judge.check(f"answer_opponent_{name.lower()}_coach",
                    contains_phrase(answer, coach),
                    f"expected head coach {coach}")
        judge.check(f"answer_opponent_{name.lower()}_stadium",
                    contains_phrase(answer, stadium),
                    f"expected {stadium}")
        judge.check(f"answer_opponent_{name.lower()}_kickoff",
                    contains_time(answer, kickoff),
                    f"expected the {kickoff} ET kickoff")
    judge.check("answer_combined_2_2", contains_record(answer, *COMBINED),
                "expected the combined record 2-2 (0-2 plus 2-0)")
    # DB after-state: exactly two newsletter signup rows
    rows = newsletter_rows(after_db)
    judge.check("two_newsletter_rows", len(rows) == 2, f"newsletter_signups={rows!r}")
    if rows:
        got = {(r["email"].lower(), r["team_abbr"]) for r in rows}
        want = {(EMAIL_1, TEAM_1), (EMAIL_2, TEAM_2)}
        judge.check("newsletter_rows_correct", got == want,
                    f"got={got!r}, want={want!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("newsletter_signups",))
    check_precise_delta(judge, initial_db, after_db, "users", "id")
    check_precise_delta(judge, initial_db, after_db, "newsletter_signups", "id",
                        added_keys=(1, 2))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
