#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--8.

Search a one-way flight Dublin -> Athens Dec 30 for 1 adult and analyze the price graph for the next 2 months.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights DUB->ATH depart 12-30 | nav /tools/price-graph for the same route anchored at 12-30 | the answer states the lowest price ($196, both the route's lowest fare and the graph's LOWEST stat)
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


GROUND_TRUTH = {"min_price": 196.0, "airline": "Spirit"}

FROM = ["dublin", "dub"]
TO = ["athens", "ath", "athens greece"]


def _graph_nav(traj):
    for q in graph_queries(traj):
        if (q_has_value(q, "from", FROM) and q_has_value(q, "to", TO)
                and q_matches_date(q, "depart", "12-30")):
            return True
    return False


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "12-30"),
            "expected /flights search Dublin->Athens depart 12-30")
    j.check("nav_price_graph", _graph_nav(traj),
            "expected the price-graph page for Dublin->Athens anchored at 12-30")
    j.check("answer_lowest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected the $196 lowest price; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--8", main)
