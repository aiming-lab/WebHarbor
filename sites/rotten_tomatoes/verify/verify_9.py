#!/usr/bin/env python3

from verify_lib import (Judge, changed_tables, check_common, clicked_transition,
                        contains_all, entered_sequence, entered_text, final_answer,
                        load_run, parse_args, resolve_db, row_dicts,
                        schema_unchanged, visited_path)

TASK_ID = 'RottenTomatoes--9'
EMAIL = 'bob.c@test.com'
PASSWORD = 'TestPass123!'
NAME = 'Robert Clark'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    before = row_dicts(initial, 'SELECT * FROM users ORDER BY id') if initial else []
    observed = row_dicts(after, 'SELECT * FROM users ORDER BY id') if after else []
    expected = [dict(row) for row in before]
    for row in expected:
        if row['email'] == EMAIL:
            row['name'] = NAME
    judge.check('only_users_table_changed', bool(initial and after) and changed_tables(initial, after) == {'users'},
                repr(changed_tables(initial, after)) if initial and after else '')
    judge.check('schema_unchanged', schema_unchanged(initial, after), 'complete sqlite_master comparison')
    judge.check('only_requested_name_changed', observed == expected and observed != before, f'before={before} after={observed}')
    judge.check('login_fields_submitted', entered_sequence(trajectory, (EMAIL, PASSWORD), '/login'), EMAIL)
    judge.check('login_redirected', clicked_transition(trajectory, '/login', '/'), 'login to home')
    judge.check('opened_account_settings', visited_path(trajectory, '/account') and
                clicked_transition(trajectory, '/account', '/account/edit'), 'account to settings')
    judge.check('submitted_exact_name', entered_text(trajectory, NAME, '/account/edit') and
                clicked_transition(trajectory, '/account/edit', '/account'), NAME)
    judge.check('answer_confirms_name', contains_all(answer, (NAME,)), repr(answer))
    judge.emit()


if __name__ == '__main__':
    main()
