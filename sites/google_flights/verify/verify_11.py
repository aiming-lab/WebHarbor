#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--11.

Compare round-trip prices New York -> Tokyo departing Feb 10, returning Feb 24, and select the option with the least number of stops.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Tokyo depart 02-10 return 02-24 | the answer selects a nonstop option as a consistent (airline, price) pair and characterizes it as nonstop/direct
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


GROUND_TRUTH = {"nonstop_pairs": [["Air France", 469.0], ["KLM", 497.0], ["Air France", 522.0], ["Spirit", 522.0], ["ANA", 526.0], ["American Airlines", 530.0], ["United", 533.0], ["Emirates", 548.0], ["ANA", 552.0], ["JetBlue", 556.0], ["Emirates", 577.0], ["Cathay Pacific", 584.0], ["Singapore Airlines", 593.0], ["Emirates", 624.0], ["British Airways", 629.0], ["Cathay Pacific", 641.0], ["Lufthansa", 650.0], ["JetBlue", 655.0], ["Spirit", 655.0], ["Turkish Airlines", 673.0], ["United", 688.0], ["Singapore Airlines", 703.0], ["Iberia", 715.0], ["Air Canada", 724.0], ["Frontier", 739.0], ["United", 757.0], ["Lufthansa", 759.0], ["Singapore Airlines", 771.0], ["Air France", 783.0], ["Etihad", 801.0], ["Air Canada", 825.0], ["British Airways", 829.0], ["Etihad", 837.0], ["JetBlue", 887.0], ["Cathay Pacific", 895.0], ["Singapore Airlines", 907.0], ["Lufthansa", 912.0], ["Delta", 928.0], ["Cathay Pacific", 943.0], ["Turkish Airlines", 956.0], ["American Airlines", 997.0], ["ANA", 1020.0], ["Southwest", 1020.0], ["Qatar Airways", 1057.0], ["Southwest", 1079.0], ["Air Canada", 1081.0], ["American Airlines", 1151.0], ["Etihad", 1153.0], ["ANA", 1286.0], ["Iberia", 1287.0], ["Frontier", 1288.0], ["Etihad", 1290.0], ["Qantas", 1308.0], ["Emirates", 1331.0], ["Qantas", 1346.0], ["Air Canada", 1347.0], ["JetBlue", 1413.0], ["Iberia", 1438.0], ["Turkish Airlines", 1457.0], ["Alaska Airlines", 1470.0], ["United", 1611.0], ["Spirit", 1705.0], ["United", 1707.0], ["Etihad", 1821.0], ["United", 1889.0], ["United", 2352.0], ["Air Canada", 2400.0]], "min_stops": 0}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-10", return_md="02-24"),
            "expected /flights NYC->Tokyo depart 02-10 return 02-24")
    n = sum(1 for a, p in GROUND_TRUTH["nonstop_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_selects_nonstop_option", n >= 1,
            f"{n} consistent nonstop (airline, price) pairs; final={ans!r}")
    j.check("answer_says_nonstop", mentions_stops(ans, 0),
            f"the selected option must be characterized as nonstop; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--11", main)
