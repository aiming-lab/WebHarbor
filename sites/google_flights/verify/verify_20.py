#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--20.

Book a round trip San Francisco -> Berlin departing Mar 5, returning Mar 12, and find the option with the shortest total travel time.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights SFO->Berlin depart 03-05 return 03-12 | shortest-total option: Alaska Airlines, 16h 00m round-trip total (7h 31m outbound) | airline mention
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


GROUND_TRUTH = {"airline": "Alaska Airlines", "total_min": 960, "out_duration": 451, "shortest_ids": [126037], "return_airline": "British Airways"}

FROM = ["san francisco", "sfo"]
TO = ["berlin", "ber"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-05", return_md="03-12"),
            "expected /flights SFO->Berlin depart 03-05 return 03-12")
    opened = opened_flight_ids(traj)
    time_reported = (mentions_duration(ans, GROUND_TRUTH["total_min"])
                     or mentions_duration(ans, GROUND_TRUTH["out_duration"]))
    if not time_reported:
        # selection-evidence branch: the run opened the shortest option's
        # detail page, names its airline, and characterizes it as the shortest
        import re as _re
        time_reported = (set(GROUND_TRUTH["shortest_ids"]) & opened
                         and mentions_airline(ans, GROUND_TRUTH["airline"])
                         and bool(_re.search(r"shortest|fastest|quickest|least travel time",
                                             ans, _re.I)))
    j.check("answer_shortest_total_time", time_reported,
            f"expected 16h 00m round-trip total (or 7h 31m outbound), or the "
            f"GT-shortest flight's detail page opened + airline + shortest "
            f"characterization; final={ans!r}")
    j.check("answer_airline_of_shortest",
            mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Alaska Airlines; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--20", main)
