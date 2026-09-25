"""Verify NFL--16: Build a Patrick Mahomes media catch-up from NFL.com search. Find the most recent news report, give its title, author and date, and summarize two facts from the story. Choose three relevant video results to accompany it and identify their titles and channels.

Expected facts below are from the captured site fixture."""
from verify_lib import Judge, check_read_only_db, check_trajectory_identity, contains_all, contains_amount, contains_phrase, contains_record, final_answer, navigated_to, run_verifier
TASK_ID = 'NFL--16'
VIDEO_CANDIDATES = [('patrick-mahomes-s-best-plays-from-3-td-game-week-2', "Patrick Mahomes's best plays from 3-TD game | Week 2", 'game-highlights'), ('mahomes-30-yard-loft-to-thornton-gets-chiefs-into-colts-territory-in-overtime', "Mahomes' 30-yard loft to Thornton gets Chiefs into Colts' territory in overtime", 'game-highlights'), ('jerry-tillery-burns-his-former-team-as-he-sacks-mahomes-in-overtime', 'Jerry Tillery burns his former team as he sacks Mahomes in overtime', 'game-highlights'), ('mahomes-18-yard-connection-with-kelce-gets-chiefs-inside-the-red-zone', "Mahomes' 18-yard connection with Kelce gets Chiefs inside the red zone", 'game-highlights'), ('can-t-miss-play-mahomes-45-yard-launch-to-thornton-gets-chiefs-to-doorstep-of-goal-line', "Can't-Miss Play: Mahomes' 45-yard launch to Thornton gets Chiefs to doorstep of goal line", 'game-highlights'), ('deforest-buckner-bulldozes-mahomes-into-the-ground-for-third-down-sack-before-halftime', 'DeForest Buckner bulldozes Mahomes into the ground for third-down sack before halftime', 'game-highlights'), ('mahomes-fastball-to-rashee-rice-yields-30-yard-gain-for-chiefs-against-colts', "Mahomes' fastball to Rashee Rice yields 30-yard gain for Chiefs against Colts", 'game-highlights'), ('first-mahomes-to-kelce-td-connection-of-2026-season-gives-chiefs-lead-vs-colts', 'First Mahomes-to-Kelce TD connection of 2026 season gives Chiefs lead vs. Colts', 'game-highlights'), ('patrick-mahomes-first-pass-of-night-is-16-yard-strike-to-xavier-worthy-in-colts-territory', "Patrick Mahomes' first pass of night is 16-yard strike to Xavier Worthy in Colts' territory", 'game-highlights'), ('is-patrick-mahomes-still-the-face-of-the-league-gmfb', "Is Patrick Mahomes still the face of the league? | 'GMFB'", 'good-morning-football'), ('what-do-you-expect-to-see-in-patrick-mahomes-return-following-knee-injury-gmfb', "What do you expect to see in Patrick Mahomes' return following knee injury? | 'GMFB'", 'good-morning-football')]
MOST_RECENT_NEWS = 'NFL QB rankings, Week 3: Patrick Mahomes, Dak Prescott, Matthew Stafford heating up'
AUTHOR = 'Nick Shook'
BODY_FACTS = ('knee injury', '133')
PLAYER_PAGE = ('Chiefs', '15')
COACH = 'Andy Reid'
STANDING = ('1st', 'AFC WEST')

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check('visited_search_mahomes', navigated_to(traj, '/search') and navigated_to(traj, 'Mahomes'), 'required: /search?q=Mahomes')
    judge.check('visited_most_recent_article', navigated_to(traj, 'nfl-qb-rankings-index-week-3'), 'required: the most recent Mahomes news article')
    judge.check('answer_most_recent_title', contains_phrase(answer, 'QB rankings') or contains_phrase(answer, MOST_RECENT_NEWS), f'expected the most recent article {MOST_RECENT_NEWS!r}')
    judge.check('answer_article_author', contains_phrase(answer, AUTHOR), f'expected the author {AUTHOR}')
    judge.check('answer_article_date', 'sep' in answer.lower() and '23' in answer, 'expected the Sep 23, 2026 publish date')
    missing_facts = [f for f in BODY_FACTS if f not in answer]
    judge.check('answer_two_body_facts', not missing_facts, f'expected two facts from the body (knee injury recovery; 8-of-9 for 133 yards vs man coverage); missing {missing_facts!r}')
    matched = [(slug, title, channel) for slug, title, channel in VIDEO_CANDIDATES
               if navigated_to(traj, '/videos/' + slug)
               and contains_phrase(answer, title)
               and contains_phrase(answer, channel.replace('-', ' '))]
    judge.check('three_named_viewed_videos', len(matched) >= 3,
                'Name three distinct viewed search videos with their channels')
    check_read_only_db(judge, initial_db, after_db)
if __name__ == '__main__':
    run_verifier(TASK_ID, run_checks)
