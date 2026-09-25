"""Verify MTA--19: Help David follow up on problems at 21 St-Queensbridge. Sign in as david.k@test.com (TestPass123!) and check his existing mezzanine-lighting complaint. The fare machine there also keeps rejecting MetroCards: check the current MetroCard guidance, submit a report about the machine on his behalf, and confirm the status and references of both complaints in his account.

Expected facts below are from the captured site fixture."""
from verify_lib import FIRST_CASE_REF, added_rows, check_only_tables_changed, check_seed_contract, check_trajectory_identity, contains_phrase, contains_ref, final_answer, navigated_to_path, run_verifier
TASK_ID = 'MTA--19'
SEEDED_CASE = 'CS-26095281'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check('visited_login', navigated_to_path(traj, '/account/login'), 'required: /account/login')
    judge.check('visited_cases_page', navigated_to_path(traj, '/account/cases'), 'required: /account/cases (check the lighting case)')
    judge.check('visited_feedback_form', navigated_to_path(traj, '/contact-us/feedback'), 'required: /contact-us/feedback')
    judge.check('answer_seeded_case_status', contains_ref(answer, SEEDED_CASE) and contains_phrase(answer, 'open'), f'{SEEDED_CASE} is currently Open')
    judge.check('answer_new_case_number', contains_ref(answer, FIRST_CASE_REF), f'the new case number is {FIRST_CASE_REF}')
    added = added_rows(after_db, initial_db, 'feedback_cases', 'case_ref')
    judge.check('one_case_added', len(added) == 1, f'added cases={[r['case_ref'] for r in added]!r}')
    if added:
        c = added[0]
        judge.check('added_case_ref', c['case_ref'] == FIRST_CASE_REF, f'case_ref={c['case_ref']!r}, expected {FIRST_CASE_REF}')
        judge.check('added_case_category', (c['category'] or '').lower() == 'station or facility', f'category={c['category']!r}')
        judge.check('added_case_about_fare_machine', 'fare machine' in (c['subject'] or '').lower() or 'fare machine' in (c['message'] or '').lower() or 'metrocard' in (c['message'] or '').lower(), f'subject={c['subject']!r}')
        judge.check('added_case_station_mentioned', '21 st-queensbridge' in (c['subject'] or '').lower() or '21 st-queensbridge' in (c['message'] or '').lower(), 'the report must name 21 St-Queensbridge')
        judge.check('added_case_status_open', c['status'] == 'Open', f'status={c['status']!r}')
    judge.check('visited_fares_page', navigated_to_path(traj, '/fares-tolls/subway-bus'), 'required: /fares-tolls/subway-bus (MetroCard status)')
    judge.check('answer_metrocard_sunset', contains_phrase(answer, 'january 1, 2026') and (contains_phrase(answer, 'no longer buy') or contains_phrase(answer, 'no longer') or contains_phrase(answer, 'cannot buy')), 'as of January 1, 2026 MetroCards can no longer be bought or refilled')
    judge.check('answer_both_cases_confirmed', contains_ref(answer, SEEDED_CASE) and contains_ref(answer, FIRST_CASE_REF), 'both cases appear with the new case number')
    check_only_tables_changed(judge, initial_db, after_db, ('feedback_cases',))
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
