#!/usr/bin/env python3
"""Verifier for B&H Photo--18: Carol turns SMS pickup alerts on."""
from verify_lib import (Judge, account_fields, changed_tables_excluding, check_common,
                        load_run, login_submitted_as, only_allowed_tables_changed,
                        parse_args, resolve_db, submitted_from_path, visited_path)

TASK_ID = 'B&H Photo--18'
EMAIL = 'carol.d@test.com'
ALLOWED = ['users', 'search_logs']


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')
    if not (initial and after):
        judge.emit()

    before = account_fields(initial, EMAIL)
    now = account_fields(after, EMAIL)
    judge.check('ground_truth_sms_started_off', not before.get('sms_opt_in'),
                f'before={before.get("sms_opt_in")}')
    judge.check('signed_in_as_the_named_account', login_submitted_as(trajectory, EMAIL), EMAIL)
    judge.check('opened_account_settings', visited_path(trajectory, '/account/edit'), '/account/edit')
    judge.check('saved_the_settings_form', submitted_from_path(trajectory, '/account/edit'),
                'a POST transition away from /account/edit')
    judge.check('sms_alerts_are_on_afterwards', bool(now.get('sms_opt_in')),
                f'after={now.get("sms_opt_in")}')
    unchanged = {field: (before.get(field), now.get(field)) for field in
                 ('display_name', 'company', 'role', 'preferred_store')
                 if before.get(field) != now.get(field)}
    judge.check('other_account_fields_unchanged', not unchanged, f'changed={unchanged}')
    judge.check('no_unrelated_state_written',
                only_allowed_tables_changed(initial, after, ALLOWED),
                f'changed={sorted(changed_tables_excluding(initial, after, ALLOWED))}')
    judge.emit()


if __name__ == '__main__':
    main()
