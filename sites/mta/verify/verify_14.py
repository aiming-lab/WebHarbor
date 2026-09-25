"""Verify MTA--14: Prepare a briefing for covering the next MTA Board meeting. Confirm the committee and board dates against the calendar and recent meeting announcement, the usual venue and how the public can watch. Identify two current board members with their titles and the Chair and CEO so I know who will be involved.

Expected facts below are from the captured site fixture."""
from verify_lib import check_read_only, check_seed_contract, check_trajectory_identity, contains_any_phrase, contains_count, contains_phrase, final_answer, navigated_to, navigated_to_path, run_verifier
TASK_ID = 'MTA--14'
BOARD_MEMBERS = ['andrew albert', 'gerard bringmann', 'samuel chu', 'michael fleischer', 'daniel garodnick', 'randolph glucksman', 'melanie hartzog', 'marc herbst', 'david r. jones', 'christopher leathers', 'blanca p. lopez', 'haeda b. mihaltses', 'melva m. miller', "james o'donnell", 'matt rand', 'john-ross rizzo', 'janette sadik-khan', 'john samuelsen', 'lisa sorin', 'edward valente', 'neal zuckerman']
EXEC_TITLES = ['chair and ceo', 'chair', 'ceo', 'member']

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check('visited_board_meetings', navigated_to_path(traj, '/transparency/board-and-committee-meetings'), 'required: /transparency/board-and-committee-meetings')
    judge.check('visited_board_members_or_leadership', navigated_to_path(traj, '/transparency/leadership/board-members') or navigated_to_path(traj, '/transparency/leadership/executive-leadership'), 'required: a board-members / executive-leadership page')
    judge.check('visited_press_release', navigated_to(traj, '/press-release/mta-committee-and-board-meetings'), 'required: a press-release article page')
    judge.check('answer_sept_28', contains_phrase(answer, 'september 28'), 'next committee/board meetings: Monday, September 28, 2026')
    judge.check('answer_sept_30', contains_phrase(answer, 'september 30'), 'and Wednesday, September 30, 2026')
    judge.check('answer_location_2_broadway', contains_phrase(answer, '2 broadway'), 'meetings are held at the MTA Board Room, 2 Broadway, 20th Floor')
    named = [m for m in BOARD_MEMBERS if m in answer.lower()]
    judge.check('answer_two_board_members', len(named) >= 2, f'must name two board members (found: {named[:4]})')
    judge.check('answer_titles', any((t in answer.lower() for t in EXEC_TITLES)), 'must give titles (e.g. Chair and CEO / Member)')
    judge.check('answer_watch_livestream', contains_any_phrase(answer, ['livestream', 'live stream', 'webcast', 'recordings', 'streaming', 'streamed', 'watch online']), 'meetings are livestreamed and recordings are posted')
    judge.check('chair_ceo', contains_phrase(answer, 'Janno Lieber') and contains_phrase(answer, 'chair') and contains_phrase(answer, 'ceo'), 'Janno Lieber, Chair and CEO')
    check_read_only(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
