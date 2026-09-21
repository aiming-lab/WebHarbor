#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--39.

Find a one-way flight Prague -> a city in Japan on Mar 20 and decide which is cheaper: Tokyo or the Hokkaido city (Sapporo).

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights PRG->Tokyo depart 03-20 AND /flights PRG->Sapporo depart 03-20 | the answer states both lowest fares ($385 Tokyo, $468 Sapporo) and the verdict that Tokyo is cheaper
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


GROUND_TRUTH = {"tokyo_min": 385.0, "sapporo_min": 468.0, "cheaper_city": "Tokyo", "tokyo_airline": "Qantas", "sapporo_airline": "American Airlines"}

FROM = ["prague", "prg"]
TO_TOKYO = ["tokyo", "hnd", "nrt", "narita", "haneda", "tokyo narita", "tokyo haneda"]
TO_SAPPORO = ["sapporo", "cts"]

import re


def main(j, traj, ans):
    j.check("nav_search_tokyo", nav_search(traj, FROM, TO_TOKYO, "03-20"),
            "expected /flights Prague->Tokyo depart 03-20")
    j.check("nav_search_sapporo", nav_search(traj, FROM, TO_SAPPORO, "03-20"),
            "expected /flights Prague->Sapporo depart 03-20")
    j.check("answer_tokyo_fare", mentions_price(ans, GROUND_TRUTH["tokyo_min"]),
            f"expected the Tokyo lowest fare $385; final={ans!r}")
    j.check("answer_sapporo_fare", mentions_price(ans, GROUND_TRUTH["sapporo_min"]),
            f"expected the Sapporo lowest fare $468; final={ans!r}")
    low = ans.casefold()
    tokyo_cheaper = (("tokyo" in low) and re.search(
        r"(cheaper|less expensive|lower|more affordable|lowest|best price)[^.\n]{0,80}tokyo"
        r"|tokyo[^.\n]{0,80}(cheaper|less expensive|lower|more affordable|lowest|best price)",
        low))
    sapporo_pricier = (("sapporo" in low or "hokkaido" in low) and re.search(
        r"(more expensive|higher|pricier|costs more)[^.\n]{0,80}(sapporo|hokkaido)"
        r"|(sapporo|hokkaido)[^.\n]{0,80}(more expensive|higher|pricier|costs more)",
        low))
    j.check("answer_verdict_tokyo_cheaper",
            bool(tokyo_cheaper or sapporo_pricier),
            f"the answer must conclude Tokyo is the cheaper city; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--39", main)
