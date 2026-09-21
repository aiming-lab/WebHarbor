#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--24.

Compare economy round-trip prices Dubai -> Rome Mar 1..8 and select the option with the fewest stops.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights DXB->FCO depart 03-01 return 03-08 | fewest-stops option: a nonstop (airline, price) pair characterized as nonstop
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


GROUND_TRUTH = {"nonstop_pairs": [["Air France", 578.0], ["Japan Airlines", 437.0], ["Qantas", 493.0], ["Air Canada", 517.0], ["Emirates", 525.0], ["Singapore Airlines", 552.0], ["JetBlue", 560.0], ["Air Canada", 577.0], ["United", 686.0], ["Japan Airlines", 837.0], ["Southwest", 829.0], ["Japan Airlines", 841.0], ["Lufthansa", 868.0]], "nonstop_count": 13}

FROM = ["dubai", "dxb"]
TO = ["rome", "fco"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "03-01", return_md="03-08"),
            "expected /flights Dubai->Rome depart 03-01 return 03-08")
    n = sum(1 for a, p in GROUND_TRUTH["nonstop_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    j.check("answer_selects_nonstop", n >= 1,
            f"{n} consistent nonstop (airline, price) pairs; final={ans!r}")
    j.check("answer_says_nonstop", mentions_stops(ans, 0),
            f"the selected option must be characterized as nonstop; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--24", main)
