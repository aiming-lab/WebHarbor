#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--4.

Search one-way flights New York -> London on Dec 26 and filter to non-stop only.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->London depart 12-26 WITH the nonstop filter (max_stops=0) | the answer presents >=3 of the nonstop options as (airline, price) pairs
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


GROUND_TRUTH = {"nonstop_count": 62, "pairs": [["Qatar Airways", 486.0], ["Emirates", 583.0], ["ANA", 553.0], ["Air Canada", 334.0], ["Japan Airlines", 729.0], ["British Airways", 438.0], ["Lufthansa", 633.0], ["Japan Airlines", 304.0], ["Air France", 765.0], ["British Airways", 348.0], ["JetBlue", 734.0], ["Spirit", 683.0], ["ANA", 461.0], ["Air France", 513.0], ["Southwest", 637.0], ["Spirit", 652.0], ["Singapore Airlines", 492.0], ["Etihad", 707.0], ["Qantas", 771.0], ["Lufthansa", 466.0], ["Japan Airlines", 789.0], ["Alaska Airlines", 651.0], ["Air France", 751.0], ["Air Canada", 498.0], ["Iberia", 707.0], ["Alaska Airlines", 674.0], ["Delta", 1015.0], ["Qatar Airways", 1017.0], ["JetBlue", 422.0], ["United", 1092.0], ["Qatar Airways", 575.0], ["Southwest", 406.0], ["Southwest", 700.0], ["Spirit", 534.0], ["Frontier", 489.0], ["KLM", 791.0], ["Qatar Airways", 836.0], ["KLM", 678.0], ["Air France", 595.0], ["Air France", 643.0], ["American Airlines", 736.0], ["Cathay Pacific", 545.0], ["Emirates", 1101.0], ["Frontier", 1186.0], ["Qatar Airways", 1246.0], ["ANA", 1004.0], ["American Airlines", 822.0], ["Southwest", 964.0], ["Japan Airlines", 662.0], ["Alaska Airlines", 468.0], ["United", 1153.0], ["Qatar Airways", 1198.0], ["JetBlue", 864.0], ["JetBlue", 692.0], ["Delta", 681.0], ["Cathay Pacific", 649.0], ["Delta", 672.0], ["American Airlines", 1206.0], ["Lufthansa", 858.0], ["United", 1371.0], ["ANA", 1067.0], ["Southwest", 745.0]]}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["london", "lhr", "lgw", "heathrow", "gatwick", "london heathrow", "london gatwick"]


def main(j, traj, ans):
    j.check("nav_search_nonstop_filter",
            nav_search(traj, FROM, TO, "12-26", max_stops=0),
            "expected /flights NYC->London 12-26 with the Nonstop-only filter applied")
    n = sum(1 for a, p in GROUND_TRUTH["pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    content = n >= 3
    if not content:
        content = configuration_reading(
            traj, ans, nav_search(traj, FROM, TO, "12-26", max_stops=0),
            [p for _a, p in GROUND_TRUTH["pairs"]],
            [a for a, _p in GROUND_TRUTH["pairs"]],
            mentions_stops(ans, 0))
    j.check("answer_presents_nonstop_options", content,
            f"{n} consistent (airline, price) pairs of the {len(GROUND_TRUTH['pairs'])} "
            f"nonstop options, or a nonstop-configuration answer with no contradicting "
            f"facts; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--4", main)
