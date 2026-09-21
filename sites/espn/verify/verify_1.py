#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--1.

Check the latest articles on ESPN for updates on any trades that occurred in
the NBA within the past 2 days.

Ground truth (hardcoded; frozen from the served mirror pages — mirror "today"
is pinned to April 10, 2024, so "past 2 days" = April 8-10):
    No NBA TRADE happened in that window; the latest trade-flavored article is
    'NBA trade deadline: biggest moves and winners' (Feb 8, 2024: OG Anunoby
    Toronto->New York, Bogdan Bogdanovic Atlanta->Phoenix, Pascal Siakam
    ->Indiana) and the latest trade on the /nba/transactions page is James
    Harden 76ers->Clippers (2023-10-31).  Player movements dated inside the
    window (Apr 8-10): Caleb Martin 4-year extension (Heat, Apr 9), Aaron
    Gordon $130M extension (Nuggets, Apr 9), OG Anunoby extension agreement
    (Knicks, Apr 8), LeBron James contract-extension talks (Lakers, Apr 8),
    Tobias Harris day-to-day (76ers, Apr 9).

Checks: run-package gate + answer + navigation (NBA news / transactions /
article pages) + EITHER >=2 real trade-or-movement facts from the anchor set
OR the honest no-trades characterization (an explicit no-trades-in-window
claim supported by the transaction categories actually on the page: injury /
contract / signing / extension / waive rows) + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, contains_all, contains_any,
                        num_in, norm, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--1', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_news_or_transactions",
            navigated_any(t, ["/nba/news", "/transactions", "/story/"]),
            "must read NBA news, the transactions page, or a trade article")
    anchors = [
        ("harden_clippers_trade", contains_all(fa, ["harden", "clippers"])),
        ("anunoby", contains_all(fa, ["anunoby"]) and
            contains_any(fa, ["knick", "new york", "traded", "extension", "raptor", "toronto"])),
        ("siakam", contains_all(fa, ["siakam"]) and
            contains_any(fa, ["pacer", "indiana"])),
        ("bogdanovic", contains_all(fa, ["bogdanovic"])),
        ("caleb_martin", contains_all(fa, ["caleb", "martin"])),
        ("aaron_gordon", contains_all(fa, ["gordon"]) and
            (num_in(fa, 130) or contains_any(fa, ["nugget", "aaron"]))),
        ("lebron_contract", contains_all(fa, ["lebron"]) and
            contains_any(fa, ["contract", "extension"])),
        ("dinwiddie", contains_all(fa, ["dinwiddie"])),
        ("portis", contains_all(fa, ["portis"]) and
            contains_any(fa, ["buck", "milwaukee", "re-sign", "resign"])),
        ("bridges_extension", contains_all(fa, ["bridges"]) and
            (num_in(fa, 90) or contains_any(fa, ["extension", "knick"]))),
        ("tatum_extension", contains_all(fa, ["tatum"]) and
            (num_in(fa, 163) or contains_any(fa, ["supermax", "extension"]))),
    ]
    matched = [name for name, ok in anchors if ok]
    f = norm(fa)
    no_trade_claim = ("no nba trades" in f) or ("no trades" in f) \
        or ("none of the" in f and "trade" in f) or ("no trade " in f) \
        or ("trades occurred" in f and f.strip().startswith("no"))
    category = contains_any(fa, ["injur", "contract", "signing", "sign ",
                                 "extension", "waiv", "day-to-day", "day to day"])
    ok = len(matched) >= 2 or (no_trade_claim and (len(matched) >= 1 or category))
    j.check("answer_trade_update", ok,
            f"specific facts={matched}; no-trade claim={no_trade_claim}, "
            f"transaction categories on page={category}")
    j.emit()

if __name__ == "__main__":
    main()
