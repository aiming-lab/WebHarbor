"""Verify NFL--11: Put together a short video briefing for Thursday’s Falcons–Packers game. Find the Week 3 preview and summarize it with its title and channel. Include the report on the Packers running back placed on the Commissioner’s Exempt List and the recap of their Week 2 game, identifying each video so I can watch them.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_all, contains_phrase, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--11'
TNF_PREVIEW = 'Falcons vs. Packers Week 3 TNF Preview | NFL Daily'
CHANNEL = 'Latest Buzz'
DESC_TOKENS = ('Gregg Rosenthal', 'Colleen Wolfe', 'Nick Shook')
OTHER_PREVIEWS = ('Rams vs. Broncos Week 3 Preview', 'Vikings vs. Buccaneers Week 3 Preview', 'Bengals vs. Steelers Week 3 Preview', 'Chargers vs. Bills Week 3 Preview', 'Ravens vs. Cowboys Week 3 Preview', 'Eagles vs. Bears Week 3 Preview', 'Chiefs vs. Dolphins Week 3 Preview')
JACOBS_TITLE = "Packers RB Josh Jacobs has been placed on the Commissioner's Exempt List"
JACOBS_CHANNEL = 'The Insiders'
RECAP_TITLE = 'Packers vs. Jets Week 2 Recap | NFL Daily'
LLOYD_TITLE = 'LB Devin Lloyd says Week 2 game vs. Falcons was most complete NFL game of career'
FEWEST = 'Latest Buzz'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_video_hub', navigated_to(traj, '/videos'), 'required: /videos/ (the hub)')
    judge.check('visited_tnf_preview_video', navigated_to(traj, 'falcons-vs-packers-week-3-tnf-preview'), "required: the TNF preview video's page (full description)")
    judge.check('visited_jacobs_video', navigated_to(traj, 'josh-jacobs'), "required: the Jacobs Commissioner's Exempt List video")
    judge.check('answer_tnf_preview_title', contains_phrase(answer, TNF_PREVIEW), f'expected the exact title {TNF_PREVIEW!r}')
    judge.check('answer_tnf_preview_channel', contains_phrase(answer, CHANNEL), f'expected the channel {CHANNEL}')
    judge.check('answer_tnf_preview_description', all((contains_phrase(answer, t) for t in DESC_TOKENS)), f'expected the description to quote {DESC_TOKENS}')
    others = [p for p in OTHER_PREVIEWS if p in answer]
    judge.check('answer_jacobs_title', contains_phrase(answer, JACOBS_TITLE), f'expected {JACOBS_TITLE!r}')
    judge.check('answer_jacobs_channel', contains_phrase(answer, JACOBS_CHANNEL), f'expected the channel {JACOBS_CHANNEL}')
    judge.check('answer_recap_title', contains_phrase(answer, RECAP_TITLE), f'expected {RECAP_TITLE!r}')
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
