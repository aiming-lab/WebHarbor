#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--25.

Find a one-way business class flight Buenos Aires -> Amsterdam on Mar 10 and provide the details of the shortest-duration flight.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights EZE->AMS depart 03-10 with Business class | shortest-duration flight: Spirit, 5h 32m | its business-class fare ($763; the economy fare $246 is also accepted since the detail page's price card shows it)
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


GROUND_TRUTH = {"airline": "Spirit", "duration": 332, "business_price": 763.0, "economy_price": 246.0}

FROM = ["buenos aires", "eze"]
TO = ["amsterdam", "ams"]


def main(j, traj, ans):
    j.check("nav_search_business",
            nav_search(traj, FROM, TO, "03-10", cabin="Business"),
            "expected /flights EZE->AMS 03-10 with Business class selected")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Spirit; final={ans!r}")
    j.check("answer_duration", mentions_duration(ans, GROUND_TRUTH["duration"]),
            f"expected 5h 32m / 332 minutes; final={ans!r}")
    j.check("answer_fare",
            mentions_price(ans, GROUND_TRUTH["business_price"])
            or mentions_price(ans, GROUND_TRUTH["economy_price"]),
            f"expected the $763 business fare (or the $246 economy fare shown on the "
            f"detail price card); final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--25", main)
