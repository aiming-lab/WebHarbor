#!/usr/bin/env python3
from verify_lib import (
    Judge, check_common, clicked_transition, database_unchanged, final_answer,
    number_bound_to, parse_args, resolve_db, visited_in_order,
    load_run, contains_any,
)

TASK_ID = "Target--0"
ARTICLE = "/support/returns-and-exchanges"


def main() -> None:
    args = parse_args(); trajectory = load_run(args.run_dir); answer = final_answer(trajectory); judge = Judge(TASK_ID)
    check_common(judge, trajectory, TASK_ID)
    judge.check("ordered_help_article_navigation", visited_in_order(trajectory, [("/support", {}), (ARTICLE, {})]), "Support precedes article")
    judge.check("clicked_returns_article", clicked_transition(trajectory, "/support", ARTICLE), "article opened by click")
    beauty = number_bound_to(answer, 60, ("opened beauty", "beauty")) and contains_any(answer, ("day", "days"))
    owned = contains_any(answer, ("one year", "1 year", "12 months")) or (number_bound_to(answer, 365, ("target owned", "owned brands")) and contains_any(answer, ("day", "days")))
    judge.check("answer_opened_beauty_window", beauty, repr(answer))
    judge.check("answer_owned_brand_window", owned, repr(answer))
    initial = resolve_db(args.initial_db, args.container, "instance_seed"); after = resolve_db(args.after_db, args.container, "instance")
    judge.check("read_only_database_unchanged", database_unchanged(initial, after), "complete database comparison")
    judge.emit()


if __name__ == "__main__": main()
