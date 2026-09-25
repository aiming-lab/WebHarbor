#!/usr/bin/env python3
"""Verify Ohio.gov--5.

Ohio Facts chain (Government section): on the geography page the town that
marks the center point of the state, the state's approximate area in square
miles, and how many rivers and streams it says Ohio has; on the state symbols
page what the coat of arms shows on the left and on the right; on the plants
and animals page how many types of trees grow in Ohio, how many insect
species you'll find, and how many plant species it lists.

Frozen ground truth (tracked data snapshot, rendered-page verified): the
geography page says the center point of the state is Centerburg in Knox
County, Ohio covers about 44,825 square miles, and it has more than 3,300
rivers and streams. The state symbols page says the coat of arms shows a
sheaf of wheat on the left and a bundle of 17 arrows on the right. The plants
and animals page says more than 120 types of trees grow in Ohio, you'll find
more than 1,000 species of insects, and Ohio has more than 300,000 plant
species.

Knowledge-shortcut guard: the navigation gates (all three Ohio Facts pages
MUST have been opened) are load-bearing — an answer produced without opening
the pages is a memory shortcut = FAIL.
"""
import re

from verify_lib import (check_read_only, check_trajectory_identity, check_visited_path,
                        contains_phrase, final_answer, run_verifier)

TASK_ID = "Ohio.gov--5"
GEOGRAPHY = "/government/resources/ohio-facts-geography"
STATE_SYMBOLS = "/government/resources/ohio-facts-state-symbols"
PLANTS_ANIMALS = "/government/resources/ohio-facts-plants-animals"


def _has_number(answer, digits, comma_grouping=True):
    """The number appears with optional comma grouping (44,825 / 44825)."""
    plain = re.escape(str(digits))
    if re.search(rf"(?<![\d.]){plain}(?![\d.,])", answer):
        return True
    if not comma_grouping:
        return False
    grouped = f"{digits:,}"
    return re.search(rf"(?<![\d.]){re.escape(grouped)}(?![\d.,])", answer) is not None


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: all three Ohio Facts pages must be opened
    check_visited_path(judge, traj, "visited_ohio_facts_geography", GEOGRAPHY)
    check_visited_path(judge, traj, "visited_ohio_facts_state_symbols", STATE_SYMBOLS)
    check_visited_path(judge, traj, "visited_ohio_facts_plants_animals", PLANTS_ANIMALS)
    # answer: geography facts
    judge.check("answer_center_point_town", contains_phrase(answer, "centerburg"),
                "expected: the center point of the state is Centerburg")
    judge.check("answer_area_square_miles", _has_number(answer, 44825),
                "expected: Ohio covers about 44,825 square miles")
    judge.check("answer_rivers_streams", _has_number(answer, 3300),
                "expected: more than 3,300 rivers and streams")
    # answer: coat of arms left / right
    judge.check("answer_coat_of_arms_left", contains_phrase(answer, "sheaf of wheat"),
                "expected: a sheaf of wheat on the left")
    judge.check("answer_coat_of_arms_right",
                contains_phrase(answer, "arrows") and re.search(r"17\s*arrows", answer) is not None,
                "expected: a bundle of 17 arrows on the right")
    # answer: plants and animals counts
    judge.check("answer_tree_types", _has_number(answer, 120),
                "expected: more than 120 types of trees grow in Ohio")
    judge.check("answer_insect_species", _has_number(answer, 1000),
                "expected: more than 1,000 species of insects")
    judge.check("answer_plant_species", _has_number(answer, 300000),
                "expected: more than 300,000 plant species")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
