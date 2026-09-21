#!/usr/bin/env python3
"""Deterministic verifier for Google Flights task Google Flights--15.

Compare prices and total duration of non-stop flights New York -> Tokyo Narita departing Feb 12, returning Feb 26.

Checks (deterministic, no LLM, no DB — read-only search task):
nav /flights NYC->Narita depart 02-12 return 02-26 | the answer compares >=2 nonstop options as consistent (airline, price, duration) triples and characterizes them as nonstop
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


GROUND_TRUTH = {"nonstop_triples": [["Air France", 832.0, 796], ["Frontier", 823.0, 835], ["Turkish Airlines", 951.0, 808], ["Cathay Pacific", 1020.0, 790], ["United", 1158.0, 769], ["Qatar Airways", 1208.0, 771], ["Iberia", 415.0, 761], ["Qantas", 398.0, 811], ["United", 473.0, 759], ["KLM", 451.0, 814], ["British Airways", 521.0, 769], ["Etihad", 521.0, 825], ["Cathay Pacific", 585.0, 801], ["Singapore Airlines", 602.0, 808], ["Qatar Airways", 647.0, 794], ["British Airways", 648.0, 799], ["United", 643.0, 821], ["Air Canada", 647.0, 833], ["Singapore Airlines", 659.0, 805], ["Spirit", 686.0, 768], ["ANA", 702.0, 769], ["JetBlue", 700.0, 796], ["Frontier", 723.0, 759], ["American Airlines", 707.0, 815], ["Singapore Airlines", 724.0, 838], ["Air Canada", 758.0, 772], ["Spirit", 779.0, 762], ["Delta", 801.0, 765], ["Etihad", 836.0, 757], ["Qatar Airways", 823.0, 809], ["Etihad", 826.0, 822], ["Iberia", 860.0, 797], ["Cathay Pacific", 915.0, 796], ["Air France", 936.0, 815], ["Etihad", 935.0, 837], ["Iberia", 979.0, 760], ["Turkish Airlines", 977.0, 793], ["Japan Airlines", 991.0, 769], ["Cathay Pacific", 1014.0, 758], ["Air Canada", 1047.0, 752], ["United", 1099.0, 757], ["Qatar Airways", 1098.0, 762], ["Iberia", 1092.0, 824], ["British Airways", 1114.0, 814], ["American Airlines", 1163.0, 761], ["Southwest", 1175.0, 779], ["JetBlue", 1185.0, 765], ["Cathay Pacific", 1170.0, 827], ["Qatar Airways", 1186.0, 815], ["Air France", 1189.0, 832], ["Qantas", 1201.0, 813], ["Qantas", 1213.0, 786], ["Lufthansa", 1249.0, 783], ["Air Canada", 1267.0, 826], ["KLM", 1291.0, 776], ["Cathay Pacific", 1296.0, 836], ["JetBlue", 1319.0, 800], ["Frontier", 1333.0, 788], ["Alaska Airlines", 1432.0, 787], ["Singapore Airlines", 1420.0, 823], ["Emirates", 1448.0, 759], ["Singapore Airlines", 1439.0, 800], ["Lufthansa", 1550.0, 763], ["Emirates", 1601.0, 839], ["Turkish Airlines", 1629.0, 779], ["Air France", 1627.0, 807], ["Emirates", 1647.0, 770], ["Emirates", 1689.0, 794], ["Southwest", 1724.0, 765]]}

FROM = ["new york", "jfk", "lga", "ewr", "new york city", "nyc"]
TO = ["narita", "nrt", "tokyo narita", "tokyo", "hnd", "haneda"]


def main(j, traj, ans):
    j.check("nav_search", nav_search(traj, FROM, TO, "02-12", return_md="02-26"),
            "expected /flights NYC->Tokyo Narita depart 02-12 return 02-26")
    n = sum(1 for a, p, dur in GROUND_TRUTH["nonstop_triples"]
            if mentions_airline(ans, a) and mentions_price(ans, p)
            and mentions_duration(ans, dur))
    j.check("answer_compares_nonstop_options", n >= 2,
            f"{n} consistent (airline, price, duration) triples of nonstop options; "
            f"final={ans!r}")
    j.check("answer_says_nonstop", mentions_stops(ans, 0),
            f"the compared options must be characterized as nonstop; final={ans!r}")


if __name__ == "__main__":
    run("Google Flights--15", main)
