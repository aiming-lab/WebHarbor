"""Verify NFL--20: I want to follow the Chiefs’ next road stretch. Check their next two opponents and combined record, and tell me when and where those games will be played. Subscribe gameday.fan@example.com to the NFL newsletter with Kansas City Chiefs selected so I can keep following the team, and confirm the signup.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_only_tables_changed, check_precise_delta, check_trajectory_identity, contains_phrase, contains_record, contains_time, entered_identity, final_answer, navigated_to, newsletter_rows, run_verifier
TASK_ID = 'NFL--20'
EMAIL_1 = 'gameday.fan@example.com'
TEAM_1 = 'KC'
EMAIL_2 = 'tailgate.buddy@example.com'
TEAM_2 = 'MIA'
OPPONENTS = (('Dolphins', (0, 2), 'Jeff Hafley', 'Hard Rock Stadium', '13:00'), ('Raiders', (2, 0), 'Klint Kubiak', 'Allegiant Stadium', '16:25'))
COMBINED = (2, 2)

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_home_footer_form', navigated_to(traj, '/'), 'required: / (footer newsletter form)')
    judge.check('typed_both_emails', entered_identity(traj, EMAIL_1), f'required: both emails {EMAIL_1} and {EMAIL_2} typed into the form')
    judge.check('visited_chiefs_schedule', navigated_to(traj, '/teams/kansas-city-chiefs/schedule'), 'required: the Chiefs schedule (next two opponents)')
    judge.check('visited_game_centers', navigated_to(traj, 'chiefs-at-dolphins-2026-reg-3') and navigated_to(traj, 'chiefs-at-raiders-2026-reg-4'), 'required: both next-game game centers')
    judge.check('answer_confirms_signup', any((p in answer.lower() for p in ('signed up', 'signup worked', 'confirmed', "you're signed up", 'newsletter signup'))), 'the answer must confirm the newsletter signups worked')
    for name, (w, l), coach, stadium, kickoff in OPPONENTS:
        judge.check(f'answer_opponent_{name.lower()}', contains_phrase(answer, name) and contains_record(answer, w, l), f'expected {name} ({w}-{l})')
        judge.check(f'answer_opponent_{name.lower()}_kickoff', contains_time(answer, kickoff), f'expected the {kickoff} ET kickoff')
    judge.check('answer_combined_2_2', contains_record(answer, *COMBINED), 'expected the combined record 2-2 (0-2 plus 2-0)')
    rows = newsletter_rows(after_db)
    judge.check('two_newsletter_rows', len(rows) == 1, f'newsletter_signups={rows!r}')
    if rows:
        got = {(r['email'].lower(), r['team_abbr']) for r in rows}
        want = {(EMAIL_1, TEAM_1)}
        judge.check('newsletter_rows_correct', got == want, f'got={got!r}, want={want!r}')
    check_only_tables_changed(judge, initial_db, after_db, ('newsletter_signups',))
    check_precise_delta(judge, initial_db, after_db, 'users', 'id')
    check_precise_delta(judge, initial_db, after_db, 'newsletter_signups', 'id', added_keys=(1,))
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
