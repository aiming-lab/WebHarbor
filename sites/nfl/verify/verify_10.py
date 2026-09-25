"""Verify NFL--10: Help me understand the Giants’ and Bears’ quarterback injury outlook after Week 2. Find the reports about the season-ending knee surgery and hamstring injury, identify each quarterback and team, and summarize the expected absence with the report’s author and publication date. Compare the Giants update with the earlier September 22 report, identifying that report by title.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_all, contains_phrase, contains_record, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--10'
GIANTS_QB = 'Jaxson Dart'
GIANTS_ARTICLE = ('giants-qb-jaxson-dart-season-ending-knee-surgery', 'Giants QB Jaxson Dart to undergo season-ending knee surgery', 'Kevin Patra')
BEARS_QB = 'Caleb Williams'
BEARS_ARTICLE = ('bears-qb-caleb-williams-considered-week-to-week', "Bears QB Caleb Williams considered 'week to week' after suffering hamstring injury", 'Kevin Patra')
SEP22_TITLE = "NFL Network: Giants' Jaxson Dart potentially out for season after testing shows worse knee injury"
TEAMS = (('giants', 'John Harbaugh', (1, 1), '3rd', 'Titans'), ('bears', 'Ben Johnson', (1, 1), '2nd', 'Eagles'))

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_newsroom', navigated_to(traj, '/news'), 'required: /news/')
    judge.check('visited_dart_article', navigated_to(traj, GIANTS_ARTICLE[0]), 'required: the Giants QB knee-surgery article')
    judge.check('visited_williams_article', navigated_to(traj, BEARS_ARTICLE[0]), 'required: the Bears QB hamstring article')
    judge.check('visited_site_search', navigated_to(traj, '/search') and navigated_to(traj, 'Dart'), 'required: the site search for the earlier report')
    judge.check('visited_sep22_article', navigated_to(traj, 'nfl-network-giants-jaxson-dart-potentially-out-for-season'), 'required: the September 22 report')
    judge.check('answer_giants_qb', contains_phrase(answer, GIANTS_QB), f'expected {GIANTS_QB}')
    judge.check('answer_giants_injury_outlook', 'knee' in answer.lower() and 'season' in answer.lower(), 'expected the knee injury and the season-ending outlook')
    judge.check('answer_giants_article_author', contains_phrase(answer, GIANTS_ARTICLE[2]), f'expected author {GIANTS_ARTICLE[2]}')
    judge.check('answer_bears_qb', contains_phrase(answer, BEARS_QB), f'expected {BEARS_QB}')
    judge.check('answer_bears_injury_outlook', 'hamstring' in answer.lower() and 'week to week' in answer.lower(), "expected the hamstring injury and the 'week to week' outlook")
    judge.check('answer_bears_article_author', contains_phrase(answer, BEARS_ARTICLE[2]), f'expected author {BEARS_ARTICLE[2]}')
    judge.check('answer_publish_dates', 'sep' in answer.lower() and ('23' in answer or '21' in answer), 'expected the publish dates (Sep 23 / Sep 21, 2026)')
    judge.check('answer_sep22_title', contains_phrase(answer, SEP22_TITLE[:70]), f'expected the exact Sep 22 title: {SEP22_TITLE!r}')
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
