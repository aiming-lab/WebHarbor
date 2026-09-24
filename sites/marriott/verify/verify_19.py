"""Verify the Courtyard city comparison without unrelated offer lookup."""
from verify_lib import (check_trajectory_identity, check_read_only, final_answer,
                        contains_phrase, contains_count, navigated_find_hotels, run_verifier)
from reviewed_contract import amount_for, entity_text
TASK_ID = 'Marriott--19'


def run_checks(judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, TASK_ID)
    a = final_answer(traj)
    for city, hotel, rate in [('Chicago', 'Courtyard by Marriott Chicago Downtown/River North', 265),
                              ('Orlando', 'Courtyard by Marriott Orlando Downtown', 160)]:
        judge.check(city+'_search', navigated_find_hotels(traj, city, {'brand': 'CY'}), 'Courtyard search')
        judge.check(city+'_hotel', contains_phrase(a, hotel), 'cheapest property')
        judge.check(city+'_rate', amount_for(a, city, rate), 'city-specific nightly rate')
        judge.check(city+'_count', contains_count(entity_text(a, city), 1), 'one Courtyard property')
    verdict = entity_text(a, 'Orlando')
    judge.check('recommendation', any(contains_phrase(verdict, x) for x in ['cheaper', 'recommend', 'less expensive']), 'Orlando recommended')
    check_read_only(judge, initial_db, after_db)


if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
