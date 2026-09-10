#!/usr/bin/env python3

from verify_lib import (Judge, check_common, check_read_only, clicked_transition,
                        entered_sequence, final_answer, has_number, load_run,
                        normalize_text, parse_args, resolve_db, row_dicts,
                        visited_path)

TASK_ID = 'RottenTomatoes--14'
EMAIL = 'carol.d@test.com'
PASSWORD = 'TestPass123!'


def pair_line(answer, title, score):
    return any(normalize_text(title) in normalize_text(line) and has_number(line, score)
               for line in answer.splitlines())


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    ratings = row_dicts(initial, """SELECT m.slug,m.title,r.score FROM user_ratings r
        JOIN users u ON u.id=r.user_id JOIN movies m ON m.id=r.movie_id
        WHERE u.email=? ORDER BY m.slug""", (EMAIL,)) if initial else []
    watchlist = {row['slug'] for row in row_dicts(initial, """SELECT m.slug FROM watchlist_items w
        JOIN users u ON u.id=w.user_id JOIN movies m ON m.id=w.movie_id WHERE u.email=?""", (EMAIL,))} if initial else set()
    expected = [row for row in ratings if row['slug'] not in watchlist]
    judge.check('ground_truth_readable', bool(initial) and len(expected) == 1, f'expected={expected}')
    judge.check('login_fields_submitted', entered_sequence(trajectory, (EMAIL, PASSWORD), '/login'), EMAIL)
    judge.check('login_redirected', clicked_transition(trajectory, '/login', '/'), 'login to home')
    judge.check('opened_both_private_lists', visited_path(trajectory, '/user/ratings') and
                visited_path(trajectory, '/user/watchlist'), 'ratings and watchlist')
    judge.check('used_account_navigation', clicked_transition(trajectory, '/', '/account') and
                clicked_transition(trajectory, '/account', '/user/ratings') and
                clicked_transition(trajectory, '/user/ratings', '/user/watchlist'), 'account tabs')
    for row in expected:
        judge.check('answer_pair_' + row['slug'], pair_line(answer, row['title'], row['score']), repr(answer))
    extras = [row['title'] for row in ratings if row not in expected and normalize_text(row['title']) in normalize_text(answer)]
    judge.check('no_extra_rated_movies', not extras, f'extras={extras}')
    check_read_only(judge, args)
    judge.emit()


if __name__ == '__main__':
    main()
