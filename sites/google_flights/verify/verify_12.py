#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--12.

Find the best-priced round trip New York -> London leaving Dec 25, returning Jan 5, with one stop or fewer.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->London depart 12-25 return 01-05 | best price among the one-stop-or-fewer options ($307) | its airline (Southwest)
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


GROUND_TRUTH = {"min_price": 307.0, "airline": "Southwest", "stops": 1}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["london", "lhr", "lgw", "heathrow", "gatwick", "london heathrow", "london gatwick"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "12-25", return_md="01-05"),
            "expected /flights NYC->London depart 12-25 return 01-05")
    j.check("answer_best_price", mentions_price(ans, GROUND_TRUTH["min_price"]),
            f"expected $307 (cheapest with <=1 stop); final={ans!r}")
    j.check("answer_airline", mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Southwest; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--12", main)
