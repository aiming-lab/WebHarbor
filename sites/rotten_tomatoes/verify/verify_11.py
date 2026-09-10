#!/usr/bin/env python3

from verify_lib import (Judge, changed_tables, check_common, clicked_transition,
                        contains_all, entered_sequence, final_answer, has_number,
                        load_run, parse_args, resolve_db, row_dicts,
                        schema_unchanged, visited_path)

TASK_ID = 'RottenTomatoes--11'
EMAIL = 'david.k@test.com'
PASSWORD = 'TestPass123!'
TARGET = 'Deadpool & Wolverine'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    query = """SELECT w.id,w.movie_id,w.user_id,w.added_at,m.title,u.email
        FROM watchlist_items w JOIN movies m ON m.id=w.movie_id JOIN users u ON u.id=w.user_id ORDER BY w.id"""
    before = row_dicts(initial, query) if initial else []
    observed = row_dicts(after, query) if after else []
    removed = [row for row in before if row['email'] == EMAIL and row['title'] == TARGET]
    expected = [row for row in before if row not in removed]
    remaining = sum(row['email'] == EMAIL for row in observed)
    expected_remaining = sum(row['email'] == EMAIL for row in expected)
    judge.check('target_present_initially', len(removed) == 1, repr(removed))
    judge.check('only_watchlist_changed', bool(initial and after) and changed_tables(initial, after) == {'watchlist_items'},
                repr(changed_tables(initial, after)) if initial and after else '')
    judge.check('schema_unchanged', schema_unchanged(initial, after), 'complete sqlite_master comparison')
    judge.check('only_target_row_removed', observed == expected, f'expected={expected} after={observed}')
    judge.check('remaining_count_is_derived', remaining == expected_remaining, f'remaining={remaining} expected={expected_remaining}')
    judge.check('login_fields_submitted', entered_sequence(trajectory, (EMAIL, PASSWORD), '/login'), EMAIL)
    judge.check('login_redirected', clicked_transition(trajectory, '/login', '/'), 'login to home')
    judge.check('opened_watchlist', visited_path(trajectory, '/user/watchlist') and
                (clicked_transition(trajectory, '/', '/user/watchlist') or
                 clicked_transition(trajectory, '/account', '/user/watchlist')), 'authenticated navigation')
    judge.check('removed_from_watchlist_ui', clicked_transition(
        trajectory, '/user/watchlist', '/user/watchlist'), TARGET)
    judge.check('answer_remaining_total', has_number(answer, remaining) and contains_all(
        answer, ('watchlist',)), repr(answer))
    judge.emit()


if __name__ == '__main__':
    main()
