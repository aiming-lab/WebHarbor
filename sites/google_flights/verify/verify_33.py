#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--33.

Find a one-way flight Shanghai -> Vancouver on Feb 27 and compare the options by carbon dioxide emissions.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights PVG->YVR depart 02-27 | lowest-emissions option: 471 kg CO2 | its airline (Air France) | a second CO2 value from the route's emissions set (an actual comparison)
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


GROUND_TRUTH = {"min_co2": 471, "airline": "Air France", "co2_values": [471, 518, 549, 579, 607, 636, 637, 665, 665, 668, 684, 689, 693, 697, 700, 721, 786, 818, 826, 829, 855, 924]}

FROM = ["shanghai", "pvg"]
TO = ["vancouver", "yvr"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-27"),
            "expected /flights Shanghai->Vancouver depart 02-27")
    j.check("answer_lowest_co2", mentions_co2(ans, GROUND_TRUTH["min_co2"]),
            f"expected 471 kg CO2; final={ans!r}")
    j.check("answer_airline_of_lowest",
            mentions_airline(ans, GROUND_TRUTH["airline"]),
            f"expected airline Air France; final={ans!r}")
    others = [v for v in GROUND_TRUTH["co2_values"] if v != GROUND_TRUTH["min_co2"]]
    j.check("answer_compares_co2",
            any(mentions_co2(ans, v) for v in others),
            "the answer must state at least one other option's CO2 value; "
            f"final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--33", main)
