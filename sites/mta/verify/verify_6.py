"""Verify MTA--6: Help Bob budget for two more subway rides this Sunday. Sign in as bob.c@test.com (TestPass123!) and review his OMNY tap history: local and express ride counts, spending toward the local cap and the combined cap, and how much room remains under each. Cross-check the published cap rules and when the seven-day period starts, then calculate the added fare for those two rides and his resulting cap totals.

Expected facts below are from the captured site fixture."""
from verify_lib import check_read_only, check_seed_contract, check_trajectory_identity, contains_amount, contains_any_phrase, contains_count, contains_phrase, final_answer, navigated_to_path, run_verifier
TASK_ID = 'MTA--6'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check('visited_login', navigated_to_path(traj, '/account/login'), 'required: /account/login')
    judge.check('visited_omny', navigated_to_path(traj, '/account/omny'), 'required: /account/omny')
    judge.check('answer_8_local_rides', contains_count(answer, 8), '8 local rides')
    judge.check('answer_1_express_ride', contains_count(answer, 1), '1 express ride')
    judge.check('answer_24_toward_35', contains_amount(answer, 24.0), '$24.00 spent toward the $35.00 cap')
    judge.check('answer_11_room', contains_amount(answer, 11.0), '$11.00 room left before the local cap')
    judge.check('answer_725_toward_67', contains_amount(answer, 31.25), '$7.25 toward the $67.00 express-inclusive cap')
    judge.check('visited_tap_and_ride', navigated_to_path(traj, '/fares-tolls/subway-bus/tap-and-ride'), 'required: /fares-tolls/subway-bus/tap-and-ride (cap cross-check)')
    judge.check('answer_cap_amounts_35_67', contains_amount(answer, 35.0) and contains_amount(answer, 67.0), 'weekly caps: $35 (subway+local bus) and $67 (with express)')
    judge.check('answer_new_cap_period_first_tap', contains_any_phrase(answer, ['seven-day cap', '7-day cap', 'first tap', 'new cap period']), 'the first tap starts a new seven-day cap')
    judge.check('sunday_fares', contains_amount(answer, 6.0) and contains_amount(answer, 30.0) and contains_amount(answer, 37.25), 'Two extra rides cost $6: local total $30; combined total $37.25')
    judge.check('combined_headroom', contains_amount(answer, 35.75), 'Combined cap remaining: $67 - $31.25 = $35.75')
    import re
    clauses = re.split(r'[;\n]|(?<=[.!?])\s+', answer.lower())
    sunday = [c for c in clauses if ('two' in c or '2 ' in c) and 'ride' in c]
    judge.check('sunday_cost_bound', any(contains_amount(c, 6.0) and ('cost' in c or 'fare' in c) for c in sunday), 'Bind the $6 fare to the two extra rides')
    clean = answer.lower().replace('not free', '').replace("aren't free", '')
    judge.check('no_free_ride_claim', not re.search(r'rides? (?:are |would be |will be )?free|rides? (?:cost|would cost) (?:nothing|\$0(?:\.00)?)', clean), 'Do not claim the extra rides are free')
    check_read_only(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
