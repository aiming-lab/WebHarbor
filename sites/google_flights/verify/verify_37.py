#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--37.

Locate a round trip Buenos Aires -> Beijing Feb 28..Mar 3, check out one of the options, and tell whether the return flight's airline is the same as the departure flight's.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights EZE->PEK depart 02-28 return 03-03 | opened a qualifying /flight/<id> detail page | the answer states the return airline (Etihad, the cheapest reciprocal return the mirror pairs) and that it is different from the outbound airline
Ground truth is HARDCODED below, frozen from the mirror's own pages (real
Chromium browser audit cross-checked against the frozen seed inventory).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (nav_search, flights_queries, graph_queries, explore_queries,
                        q_has_value, q_matches_date, q_scalar, opened_flight_ids,
                        mentions_price, mentions_duration, mentions_airline,
                        mentions_co2, mentions_stops, consistent_pairs,
                        consistent_triples, mentions_airline_any, plain_numbers,
                        configuration_reading, foreign_airline_mentions,
                        stated_prices_consistent, run)


GROUND_TRUTH = {"return_airline": "Etihad", "outbound_ids": [126421, 126422, 126423, 126424, 126425, 126426, 126427, 126428, 126429, 126430, 126431, 126432, 126433, 126434, 126435, 126436, 126437, 126438, 126439, 126440, 126441, 126442]}

FROM = ["buenos aires", "eze"]
TO = ["beijing", "pek"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-28", return_md="03-03"),
            "expected /flights Buenos Aires->Beijing depart 02-28 return 03-03")
    opened = opened_flight_ids(traj)
    qualifying = [fid for fid in opened if fid in set(GROUND_TRUTH["outbound_ids"])]
    j.check("opened_flight_detail", bool(qualifying),
            f"opened flight ids {sorted(opened)}; expected one of the route's "
            f"{len(GROUND_TRUTH['outbound_ids'])} outbound flights")
    low = ans.casefold()
    j.check("answer_return_airline", "etihad" in low,
            f"the paired return flight is operated by Etihad; final={ans!r}")
    different = any(w in low for w in ("different", "not the same", "isn't the same",
                                       "not the same airline", "differs", "another airline",
                                       "a different airline", "no,"))
    j.check("answer_verdict_different", different,
            f"the return airline is different from the outbound airline; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--37", main)
