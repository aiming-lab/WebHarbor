"""Verify NFL--3: Help me compare the league’s top two rushers as Week 3 fantasy flex options. Identify them from the rushing leaderboard and compare their teams, yards, attempts, yards per attempt and touchdowns. Check their upcoming opponents and both teams’ records, the kickoff times and venues, and whether either rusher’s quarterback has an injury designation that could affect the matchup.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, check_visited_path, contains_all, contains_amount, contains_any, contains_phrase, contains_record, contains_time, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--3'
RUSHERS = (('walker', 'Kenneth Walker III', 'Chiefs', 290, 47, '6.2', '1', '9', '211', 'Michigan State'), ('henry', 'Derrick Henry', 'Ravens', 212, 40, '5.3', '4', '22', '252', 'Alabama'))
TEAM_PAGES = (('chiefs', 'Andy Reid', 'Arrowhead Stadium'), ('ravens', 'Jesse Minter', 'M&T Bank Stadium'))
QB_RANKS = (('mahomes', 'Mahomes', 566, '5th', ('5th', 'fifth', 'no. 5', '#5')), ('jackson', 'Lamar Jackson', 559, '6th', ('6th', 'sixth', 'no. 6', '#6')))
GAMES = (('chiefs_game', 'Dolphins', 'Hard Rock Stadium', (2, 0), (0, 2)), ('ravens_game', 'Cowboys', 'Maracana Stadium', (1, 1), (1, 1)))
QB_INJURY = 'Mahomes'
QB_STATUS = 'Full Participation'

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, 'visited_rushing_leaders', '/stats/rushing/')
    judge.check('visited_week3_game_centers', navigated_to(traj, 'chiefs-at-dolphins-2026-reg-3') and navigated_to(traj, 'ravens-at-cowboys-2026-reg-3'), 'required: both Week 3 game centers (KC@MIA and BAL@DAL)')
    judge.check('visited_injuries', navigated_to(traj, '/injuries'), "required: /injuries/ (or a game center's injury section) for the QB status")
    for tag, name, team, yds, att, ypa, tds, number, weight, college in RUSHERS:
        import re
        section = next((part for part in re.split(r'[\n;]+|(?<=[.!?])\s+', answer) if name.casefold() in part.casefold()), '')
        judge.check(f'{tag}_bound_stats', all(contains_amount(section, v) for v in (yds, att, float(ypa), int(tds))) and contains_phrase(section, team), f'Bind {name} to his team and rushing statistics')
        judge.check(f'answer_{tag}_named', contains_phrase(answer, name), f'expected {name}')
        judge.check(f'answer_{tag}_team', contains_phrase(answer, team), f'expected the {team} as his team (2026 snapshot)')
        judge.check(f'answer_{tag}_yards', contains_amount(answer, yds), f'expected {yds} rushing yards')
        judge.check(f'answer_{tag}_attempts', contains_amount(answer, att), f'expected {att} attempts')
        judge.check(f'answer_{tag}_ypa', contains_all(answer, (ypa,)), f'expected {ypa} yards per attempt')
        judge.check(f'answer_{tag}_touchdowns', contains_amount(answer, tds), f'expected {tds} rushing touchdowns')
    for tag, opponent, stadium, kc_rec, opp_rec in GAMES:
        judge.check(f'answer_{tag}_opponent', contains_phrase(answer, opponent), f'expected opponent {opponent}')
        judge.check(f'answer_{tag}_stadium', contains_phrase(answer, stadium), f'expected {stadium}')
        judge.check(f'answer_{tag}_records', contains_record(answer, *kc_rec) and contains_record(answer, *opp_rec), f'expected both records {kc_rec} and {opp_rec}')
    judge.check('answer_kc_kickoff_1pm', contains_time(answer, '13:00'), 'expected SUN 1:00pm ET kickoff for Chiefs at Dolphins')
    judge.check('answer_bal_kickoff_425pm', contains_time(answer, '16:25'), 'expected INTL SUN 4:25pm ET kickoff for Ravens at Cowboys')
    judge.check('answer_qb_on_report', contains_phrase(answer, QB_INJURY), f'expected {QB_INJURY} on the Week 3 injury report')
    judge.check('answer_qb_practice_status', contains_phrase(answer, QB_STATUS), f"expected practice status '{QB_STATUS}'")
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
