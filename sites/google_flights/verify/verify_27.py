#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--27.

Locate a one-way flight Johannesburg -> Toronto on Mar 30 and analyze the price trends for the following month.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights JNB->YYZ depart 03-30 | nav /tools/price-graph for the same route anchored at 03-30 | the answer states the lowest price ($550, the graph's LOWEST stat and the route's lowest fare)
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


GROUND_TRUTH = {"min_price": 550.0, "airline": "Qatar Airways"}

FROM = ["johannesburg", "jnb"]
TO = ["toronto", "yyz"]


def _graph_nav(traj):
    for q in graph_queries(traj):
        if (q_has_value(q, "from", FROM) and q_has_value(q, "to", TO)
                and q_matches_date(q, "depart", "03-30")):
            return True
    return False


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-30"),
            "expected /flights search Johannesburg->Toronto depart 03-30")
    j.check("nav_price_graph", _graph_nav(traj),
            "expected the price-graph page for Johannesburg->Toronto anchored at 03-30")
    j.check("answer_lowest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected the $550 lowest price; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--27", main)
