"""Verify NFL--9: Prepare a September 23 roster-movement roundup. List the practice-squad signings by team, flag the veterans and teams with multiple additions, and cover that day’s Reserve/Injured placements and waiver terminations. Give some context for the veteran tight end returning to the Eagles by locating the newsroom report and crediting its title and author.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_all, contains_any, contains_date, contains_phrase, contains_record, contains_time, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--9'
PS_PLAYERS = ('Hardy', 'Loudermilk', 'Hekker', 'Anderson', 'Pancol', 'Ross', 'Bachie', 'Harris', 'Toia', 'Meiga', 'Seumalo', 'Whitley', 'Moore II', 'Johnson', 'Cooks')
MULTI_TEAMS = ('Jets', 'Vikings', 'Seahawks')
RESERVE_LIST = ('McCrary-Ball', 'Onyemata', 'Arian Smith', 'Brooks', 'Njoku', 'Bradford', 'Pettus', 'C.J. West', 'Rivers', 'Banks')
WAIVERS = ('Gardner', 'Jennings', 'Taimani', 'Estime')
ERTZ_TITLE = 'TE Zach Ertz reuniting with Eagles'
ERTZ_AUTHOR = 'Bobby Kownack'
HEKKER = ('Hekker', 'Vikings', 'P', '15')
VIKINGS_COACH = "O'Connell"
VIKINGS_RANK_FORMS = ('1st', 'first')
VIKINGS_DIVISION = 'NFC North'
VIKINGS_DIFF = 23
W3_GAME = ('Buccaneers', '2026-09-27', '16:05')

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_transactions', navigated_to(traj, '/transactions'), 'required: /transactions/')
    judge.check('visited_reserve_list', navigated_to(traj, 'category=Reserve'), 'required: the Reserve List category')
    judge.check('visited_waivers', navigated_to(traj, 'category=Waivers'), 'required: the Waivers category')
    judge.check('visited_newsroom', navigated_to(traj, '/news'), 'required: /news/ (paginate to find the Ertz article)')
    judge.check('visited_ertz_article', navigated_to(traj, 'te-zach-ertz-reuniting-with-eagles'), 'required: the Ertz practice-squad article')
    missing = [p for p in PS_PLAYERS if not contains_phrase(answer, p)]
    judge.check('answer_all_15_ps_players', not missing, f'missing from answer: {missing!r}')
    missing_teams = [t for t in MULTI_TEAMS if not contains_phrase(answer, t)]
    judge.check('answer_multi_signing_teams', not missing_teams, f'expected Jets, Vikings and Seahawks; missing {missing_teams!r}')
    judge.check('answer_veteran_flagging', 'veteran' in answer.lower(), 'the answer must flag which signings were veteran signings')
    missing_reserve = [p for p in RESERVE_LIST if not contains_phrase(answer, p)]
    judge.check('answer_reserve_list', not missing_reserve, f"expected the day's Reserve/Injured placements; missing {missing_reserve!r}")
    missing_waivers = [p for p in WAIVERS if not contains_phrase(answer, p)]
    judge.check('answer_waiver_terminations', not missing_waivers, f"expected the day's waiver terminations; missing {missing_waivers!r}")
    judge.check('answer_ertz_title', contains_phrase(answer, ERTZ_TITLE), f'expected the article title {ERTZ_TITLE!r}')
    judge.check('answer_ertz_author', contains_phrase(answer, ERTZ_AUTHOR), f'expected the author {ERTZ_AUTHOR}')
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
