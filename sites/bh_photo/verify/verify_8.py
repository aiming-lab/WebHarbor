#!/usr/bin/env python3
"""Verifier for B&H Photo--8: report what the Q&A answer says about store pickup."""
from verify_lib import (
    Judge,
    changed_tables_excluding,
    check_common,
    final_answer,
    load_run,
    normalize_text,
    only_allowed_tables_changed,
    parse_args,
    resolve_db,
    row_dicts,
    states_pickup_policy,
    visited_path,
)

TASK_ID = 'B&H Photo--8'
SLUG = 'canon-eos-r1-mirrorless-camera-with-essentials-kit'


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
        SELECT q.question, a.answer FROM product_questions q
        JOIN product_answers a ON a.question_id = q.id
        JOIN products p ON p.id = q.product_id
        WHERE p.slug = ? AND (lower(q.question) LIKE '%counter%' OR lower(q.question) LIKE '%pickup%')
    """, (SLUG,)) if initial else []
    judge.check('ground_truth_readable', bool(rows), f'pickup questions={len(rows)}')
    if not rows:
        judge.emit()
    published = rows[0]['answer']

    judge.check('opened_qa_page', visited_path(trajectory, f'/product/{SLUG}/qa'), f'{SLUG}/qa')
    # accept a paraphrase: the answer must carry the substance, which is that
    # pickup depends on the counter stock the page shows
    normalized = normalize_text(answer)
    judge.check('answer_reports_pickup_is_offered',
                states_pickup_policy(answer),
                f'published={published!r} answer={answer!r}')
    judge.check('answer_is_not_the_question_restated',
                normalize_text(rows[0]['question']) not in normalized or len(normalized) > len(normalize_text(rows[0]['question'])) + 12,
                f'answer={answer!r}')

    if initial and after:
        judge.check('no_state_written', only_allowed_tables_changed(initial, after, ['search_logs']),
                    f'changed={sorted(changed_tables_excluding(initial, after, ["search_logs"]))}')
    judge.emit()


if __name__ == '__main__':
    main()
