"""Verify NFL--18: Which division leaders look strongest and weakest by point differential? Compare the two extremes using their divisions, records, points scored and allowed, then assess their next two matchups each using the opponents, kickoff times and stadiums from their schedules and game centers.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_amount, contains_phrase, contains_record, contains_time, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--18'
BEST_TEAM = '49ers'
BEST_DIVISION = 'NFC WEST'
BEST_RECORD = (2, 0)
BEST_PF = '62'
BEST_PA = '20'
BEST_DIFF = '42'
WORST_TEAM = 'Eagles'
WORST_DIFF = '6'
LEADERS = (('passing', 'Tyler Shough', 'Saints'), ('rushing', 'Kenneth Walker III', 'Chiefs'), ('receiving', 'Amon-Ra St. Brown', 'Lions'), ('tackles', 'Anthony Hill Jr.', 'Titans'), ('interceptions', 'Jevon Holland', 'Giants'))
DIVISION_LEADER_LEADERS = ('Walker', 'Chiefs')
EXTREMES = (('49ers_side', 'Kyle Shanahan', "Levi's", 'Cardinals', '16:05'), ('eagles_side', 'Nick Sirianni', 'Lincoln Financial Field', 'Bears', '20:15'))

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_standings', navigated_to(traj, '/standings'), 'required: /standings/')
    judge.check('visited_extreme_team_pages', navigated_to(traj, '/teams/san-francisco-49ers') and navigated_to(traj, '/teams/philadelphia-eagles'), "required: both extreme leaders' team pages")
    judge.check('visited_extreme_schedules', navigated_to(traj, '/teams/san-francisco-49ers/schedule') and navigated_to(traj, '/teams/philadelphia-eagles/schedule'), "required: both extreme leaders' schedules")
    judge.check('visited_next_game_centers', navigated_to(traj, 'cardinals-at-49ers-2026-reg-3') and navigated_to(traj, 'eagles-at-bears-2026-reg-3'), 'required: both next-game game centers')
    judge.check('answer_best_team_49ers', contains_phrase(answer, BEST_TEAM), 'expected the 49ers as the best point-differential leader')
    judge.check('answer_best_division', contains_phrase(answer, BEST_DIVISION), 'expected NFC West (rendered upper-case)')
    judge.check('answer_best_record', contains_record(answer, *BEST_RECORD), 'expected 2-0')
    judge.check('answer_best_points', BEST_PF in answer and BEST_PA in answer and (BEST_DIFF in answer), f'expected {BEST_PF} scored, {BEST_PA} allowed (+{BEST_DIFF})')
    judge.check('answer_worst_leader_eagles', contains_phrase(answer, WORST_TEAM), 'expected the Eagles as the worst point-differential leader')
    judge.check('answer_worst_differential', WORST_DIFF in answer, f'expected the +{WORST_DIFF} differential')
    for tag, coach, stadium, opponent, kickoff in EXTREMES:
        judge.check(f'answer_{tag}_next_game', contains_phrase(answer, opponent) and contains_time(answer, kickoff), f'expected the next game vs the {opponent} at {kickoff} ET')
    judge.check('worst_division_points', contains_phrase(answer, 'NFC East') and '48' in answer and '42' in answer, 'Eagles: NFC East, 48 points for and 42 against')
    for slug, opponent, time, venue in (
        ('broncos-at-49ers-2026-reg-4', 'Broncos', '16:25', "Levi's"),
        ('rams-at-eagles-2026-reg-4', 'Rams', '13:00', 'Lincoln Financial Field'),
    ):
        judge.check('visited_' + slug, navigated_to(traj, '/games/' + slug), 'Inspect the second matchup')
        import re
        section = next((part for part in re.split(r'[;\n]|(?<=[.!?])\s+', answer) if contains_phrase(part, opponent)), '')
        judge.check('second_matchup_' + opponent, contains_time(section, time) and contains_phrase(section, venue) and contains_phrase(section, 'Sunday'), 'Bind the opponent to its kickoff and venue')
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
