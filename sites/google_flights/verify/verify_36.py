#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--36.

Search round-trip flights Helsinki -> New Delhi Mar 28..Apr 4 and filter the results to show only flights under $1000.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights HEL->DEL depart 03-28 return 04-04 WITH the under-$1000 price filter (max_price) | the answer presents >=3 of the under-$1000 options as (airline, price) pairs, or the filter-configuration reading with the no-contradiction guard
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


GROUND_TRUTH = {"under_pairs": [["Singapore Airlines", 65.0], ["Air Canada", 80.0], ["Air Canada", 100.0], ["JetBlue", 110.0], ["Air Canada", 117.0], ["Qantas", 128.0], ["Etihad", 132.0], ["Cathay Pacific", 135.0], ["Air Canada", 136.0], ["Qantas", 154.0], ["Qantas", 180.0], ["Cathay Pacific", 819.0]], "under_count": 12}

FROM = ["helsinki", "hel"]
TO = ["new delhi", "delhi", "del"]


def main(j, traj, ans):
    nav_ok = nav_search(traj, FROM, TO, "03-28", return_md="04-04", max_price_le=1000)
    j.check("nav_search_under1000_filter", nav_ok,
            "expected /flights HEL->DEL 03-28/04-04 with the max_price filter applied")
    n = sum(1 for a, p in GROUND_TRUTH["under_pairs"]
            if mentions_airline(ans, a) and mentions_price(ans, p))
    import re as _re
    says_under1000 = bool(_re.search(
        r"under\s*\$?\s*1,?000|below\s*\$?\s*1,?000|less than\s*\$?\s*1,?000"
        r"|max(?:imum)?\s*price|price\s*filter", ans.casefold()))
    content = n >= 3 or configuration_reading(
        traj, ans, nav_ok,
        [p for _a, p in GROUND_TRUTH["under_pairs"]],
        [a for a, _p in GROUND_TRUTH["under_pairs"]],
        says_under1000, extra_prices=(1000.0,))
    j.check("answer_shows_under1000_options", content,
            f"{n} consistent (airline, price) pairs of the {len(GROUND_TRUTH['under_pairs'])} "
            f"options under $1000, or an under-$1000-configuration answer with no "
            f"contradicting facts; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--36", main)
