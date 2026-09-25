"""Verify NFL--8: My nephew follows Penn State running backs and wants to get to know the Eagles’ star and his current backfield. Find the player in the directory and summarize his jersey number, height, weight, experience and college. Compare the Eagles’ active running backs and quarterbacks, then explain how the team is doing and when, where and against whom he can watch their Week 3 game.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_all, contains_amount, contains_phrase, contains_record, contains_time, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--8'
PLAYER = 'Saquon Barkley'
PLAYER_FACTS = ('26', '232', 'Penn State')
COACH = 'Sirianni'
STADIUM = 'Lincoln Financial Field'
OTHER_RBS = ('Shipley', 'Bigsby')
QBS = ('Hurts', 'Dalton', 'McKee', 'Payton')
W2_FINAL = ('Titans', 24, 20)
OPPONENT = 'Bears'
KICKOFF_24H = '20:15'
GC = 'eagles-at-bears-2026-reg-3'
BEARS_COACH = 'Ben Johnson'
BEARS_STADIUM = 'Soldier Field'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_player_directory', navigated_to(traj, '/players'), 'required: the player directory (search)')
    judge.check('visited_directory_search_barkley', navigated_to(traj, 'Barkley'), 'required: the directory search for Barkley')
    judge.check('visited_barkley_page', navigated_to(traj, '/players/saquon-barkley'), 'required: /players/saquon-barkley/')
    judge.check('visited_eagles_page', navigated_to(traj, '/teams/philadelphia-eagles'), 'required: /teams/philadelphia-eagles/ (coach + stadium + record)')
    judge.check('visited_eagles_roster_filters', navigated_to(traj, '/teams/philadelphia-eagles/roster') and navigated_to(traj, 'position=RB') and navigated_to(traj, 'position=QB'), 'required: the Eagles roster with both the RB and QB filters applied')
    judge.check('visited_mnf_game_center', navigated_to(traj, GC), "required: the Eagles' Week 3 Monday-night game center")
    judge.check('answer_player_named', contains_phrase(answer, PLAYER), f'expected {PLAYER}')
    judge.check('answer_player_facts', contains_all(answer, PLAYER_FACTS), f'expected jersey #26, 232 lbs, Penn State (got tokens {PLAYER_FACTS})')
    judge.check('answer_height_6_0', contains_all(answer, ('6-0',)), 'expected height 6-0 as the site lists it')
    judge.check('answer_experience_9_years', '9' in answer and 'year' in answer.lower(), 'expected 9 years of experience')
    for name in OTHER_RBS:
        judge.check(f'answer_other_rb_{name.lower()}', contains_phrase(answer, name), f'expected the other active running back {name}')
    for name in QBS:
        judge.check(f'answer_qb_{name.lower()}', contains_phrase(answer, name), f'expected the active quarterback {name}')
    judge.check('answer_record_and_standing', contains_record(answer, 2, 0) and '1st' in answer and ('NFC' in answer), 'expected the 2-0 record and 1st NFC East standing')
    judge.check('answer_mnf_opponent', contains_phrase(answer, OPPONENT), f'expected the {OPPONENT} as the Week 3 opponent')
    judge.check('answer_mnf_kickoff', contains_time(answer, KICKOFF_24H), 'expected MON 8:15pm ET kickoff')
    judge.check('answer_mnf_stadium', contains_phrase(answer, 'Soldier Field'), 'expected Soldier Field')
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
