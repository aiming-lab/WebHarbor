#!/usr/bin/env python3

import bcrypt

from verify_lib import (Judge, changed_tables, check_common, clicked_transition,
                        contains_all, entered_sequence, final_answer, load_run,
                        parse_args, resolve_db, row_dicts, schema_unchanged,
                        visited_path)

TASK_ID = 'RottenTomatoes--8'
EMAIL = 'testreviewer@test.com'
NAME = 'Test Reviewer'
PASSWORD = 'ReviewPass456!'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    before_users = row_dicts(initial, 'SELECT * FROM users ORDER BY id') if initial else []
    after_users = row_dicts(after, 'SELECT * FROM users ORDER BY id') if after else []
    created = [row for row in after_users if row['email'] == EMAIL]
    judge.check('account_absent_initially', not [row for row in before_users if row['email'] == EMAIL], EMAIL)
    judge.check('only_users_table_changed', bool(initial and after) and changed_tables(initial, after) == {'users'},
                repr(changed_tables(initial, after)) if initial and after else '')
    judge.check('schema_unchanged', schema_unchanged(initial, after), 'complete sqlite_master comparison')
    judge.check('exact_single_user_added', len(after_users) == len(before_users) + 1 and len(created) == 1 and
                [row for row in after_users if row['email'] != EMAIL] == before_users,
                f'before={len(before_users)} after={len(after_users)}')
    judge.check('created_identity_and_password', len(created) == 1 and created[0]['name'] == NAME and
                bcrypt.checkpw(PASSWORD.encode(), created[0]['password_hash'].encode()), repr(created))
    judge.check('registration_fields_submitted', entered_sequence(
        trajectory, (NAME, EMAIL, PASSWORD, PASSWORD), '/register'), 'name, email, password, confirmation')
    judge.check('registration_redirected', clicked_transition(trajectory, '/register', '/'), 'POST form to home')
    judge.check('authenticated_account_opened', visited_path(trajectory, '/account') and
                clicked_transition(trajectory, '/', '/account'), 'home to account')
    judge.check('answer_confirms_identity', contains_all(answer, (NAME, EMAIL)), repr(answer))
    judge.emit()


if __name__ == '__main__':
    main()
