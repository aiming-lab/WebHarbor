"""Verify NFL--19: Help me distinguish the Cardinals players named Williams before their Week 3 game. Use the directory’s name and team filters to identify every matching player, with position, roster status, jersey number and college. Cross-check the Cardinals–49ers injury report to identify which of them is listed and his practice status.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_all, contains_phrase, contains_record, contains_time, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--19'
WILLIAMSES = (('Garrett', ('CB', 'ACT', '21', 'Syracuse')), ('Jayden', ('OT', 'ACT', '66', 'Mississippi')), ('Wydett', ('SAF', 'ACT', '31', 'Mississippi')), ('Damonic', ('DT', 'DEV', '96', 'Oklahoma')))
GARRETT_STATUS = 'Limited Participation'
COACH = 'Mike LaFleur'
STADIUM = 'State Farm Stadium'
QBS = ('Minshew', 'Beck', 'Brissett')
DIVISION_RANK = ('4th', 'NFC WEST')
W3 = ('4:05pm', "Levi's")

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_directory_search', navigated_to(traj, '/players') and navigated_to(traj, 'Williams') and navigated_to(traj, 'AZ'), 'required: the player directory search (Williams + Cardinals filter)')
    judge.check('visited_injuries', navigated_to(traj, '/injuries'), 'required: /injuries/ (cross-check)')
    for first, tokens in WILLIAMSES:
        judge.check(f'answer_{first.lower()}_williams', contains_all(answer, (first,) + tokens), f'expected {first} Williams with {tokens}')
    judge.check('answer_garrett_injury_status', contains_phrase(answer, 'Garrett') and contains_phrase(answer, GARRETT_STATUS), f"expected Garrett Williams with '{GARRETT_STATUS}'")
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
