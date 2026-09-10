#!/usr/bin/env python3

from verify_lib import (Judge, check_common, check_read_only, clicked_from_query,
                        contains_all, final_answer, load_run, normalize_text,
                        parse_args, resolve_db, row_dicts, visited_query)

TASK_ID = 'RottenTomatoes--3'
MOVIES = ('oppenheimer_2023', 'the_dark_knight')


def search_used(trajectory):
    return visited_query(trajectory, '/search', {'search': 'Christopher Nolan'}) or visited_query(
        trajectory, '/search', {'q': 'Christopher Nolan'})


def clicked_result(trajectory, slug):
    return clicked_from_query(trajectory, '/search', {'search': 'Christopher Nolan'}, '/m/' + slug) or clicked_from_query(
        trajectory, '/search', {'q': 'Christopher Nolan'}, '/m/' + slug)


def record_line(answer, title, date):
    return any(normalize_text(title) in normalize_text(line) and normalize_text(date) in normalize_text(line)
               for line in answer.splitlines())


def main():
    args = parse_args()
    trajectory = load_run(args.run_dir)
    judge = Judge(TASK_ID)
    answer = final_answer(trajectory)
    check_common(judge, trajectory, TASK_ID)
    initial = resolve_db(args.initial_db, args.container, 'instance_seed')
    rows = row_dicts(initial, 'SELECT slug,title,producer,release_date_streaming FROM movies WHERE slug IN (?,?)', MOVIES) if initial else []
    by_slug = {row['slug']: row for row in rows}
    producer_sets = [{name.strip() for name in by_slug[slug]['producer'].split(',') if name.strip()} for slug in MOVIES] if len(by_slug) == 2 else []
    shared = set.intersection(*producer_sets) if producer_sets else set()
    exclusive = set.union(*producer_sets) - shared if producer_sets else set()
    judge.check('ground_truth_readable', len(by_slug) == 2 and bool(shared), f'shared={sorted(shared)}')
    judge.check('searched_christopher_nolan', search_used(trajectory), 'Christopher Nolan search')
    judge.check('opened_both_results_from_search', all(clicked_result(trajectory, slug) for slug in MOVIES), repr(MOVIES))
    judge.check('all_shared_producers', contains_all(answer, sorted(shared)), repr(answer))
    producer_claims = [line for line in answer.splitlines() if any(
        token in normalize_text(line) for token in ('producer', 'credited on both', 'shared'))]
    extras = [name for name in exclusive if any(normalize_text(name) in normalize_text(line) for line in producer_claims)]
    judge.check('no_exclusive_producers', not extras, f'extras={extras}')
    for slug in MOVIES:
        row = by_slug.get(slug, {})
        judge.check('date_bound_' + slug, bool(row) and record_line(answer, row['title'], row['release_date_streaming']), repr(answer))
    check_read_only(judge, args)
    judge.emit()


if __name__ == '__main__':
    main()
