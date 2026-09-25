#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--17.

Find the cheapest round-trip flight New York -> Paris leaving Dec 27, returning Jan 10.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Paris depart 12-27 return 01-10 | cheapest fare ($423, the lowest the mirror shows for this round-trip search) | its airline
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


GROUND_TRUTH = {"min_price": 423.0, "airline": "Southwest"}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["paris", "cdg", "charles de gaulle"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "12-27", return_md="01-10"),
            "expected /flights NYC->Paris depart 12-27 return 01-10")
    j.check("answer_cheapest_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $423; final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Southwest; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--17", main)
