#!/usr/bin/env python3
"""Verifier for B&H Photo--12: the more expensive of the two carbon fibre monopods."""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    final_answer,
    load_run,
    names_product,
    normalize_text,
    only_allowed_tables_changed,
    parse_args,
    relevant_search,
    resolve_db,
    row_dicts,
    states_price,
)

TASK_ID = 'B&H Photo--12'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')

    rows = row_dicts(initial, """
        SELECT name, slug, price FROM products
        WHERE lower(name) LIKE '%carbon fiber monopod%' ORDER BY price DESC
    """) if initial else []
    judge.check('ground_truth_two_monopods', len(rows) == 2, f'monopods={[r["name"] for r in rows]}')
    if len(rows) != 2:
        judge.emit()
    dearer, cheaper = rows[0], rows[1]

    judge.check('used_catalogue_search', relevant_search(trajectory, ['carbon', 'fiber', 'monopod']),
                'the header search, or Search Within Results on a listing')
    judge.check('answer_names_the_dearer_monopod',
                names_product(answer, dearer['name']),
                f"expected={dearer['name']!r} answer={answer!r}")
    judge.check('answer_states_its_price', states_price(answer, dearer['price']),
                f"expected={dearer['price']} answer={answer!r}")
    judge.check('answer_is_not_the_cheaper_one',
                not (normalize_text(cheaper['name']) in normalize_text(answer)
                     and normalize_text(dearer['name']) not in normalize_text(answer)),
                f"cheaper={cheaper['name']!r} answer={answer!r}")

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
