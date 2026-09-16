#!/usr/bin/env python3
"""Verifier for B&H Photo--10: the kit containing the Canon EOS C80 cinema camera."""
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
    resolve_db,
    row_dicts,
    states_price,
    visited_path,
)

TASK_ID = 'B&H Photo--10'


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)

    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    after = resolve_db(args.after_db, args.container, 'instance')
    judge.check('databases_readable', bool(initial and after), f'initial={initial} after={after}')

    kits = row_dicts(initial, """
        SELECT DISTINCT b.id, b.title, b.slug, b.bundle_price FROM bundles b
        JOIN bundle_items i ON i.bundle_id = b.id JOIN products p ON p.id = i.product_id
        WHERE lower(p.name) LIKE '%eos c80%'
    """) if initial else []
    judge.check('ground_truth_single_kit', len(kits) == 1, f'kits={[k["title"] for k in kits]}')
    if len(kits) != 1:
        judge.emit()
    kit = kits[0]
    members = row_dicts(initial, """
        SELECT p.name FROM bundle_items i JOIN products p ON p.id = i.product_id
        WHERE i.bundle_id = ? ORDER BY p.name
    """, (kit['id'],))
    others = [row['name'] for row in members if 'eos c80' not in normalize_text(row['name'])]
    judge.check('ground_truth_two_other_items', len(others) == 2, f'others={others}')

    judge.check(
        'opened_the_matching_kit_page',
        visited_path(trajectory, '/bundle/' + kit['slug']),
        f"expected=/bundle/{kit['slug']}",
    )
    judge.check('answer_states_kit_price', states_price(answer, kit['bundle_price']),
                f"expected={kit['bundle_price']} answer={answer!r}")
    missing = [name for name in others if not names_product(answer, name)]
    judge.check('answer_names_both_other_items', not missing, f'missing={missing}')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
