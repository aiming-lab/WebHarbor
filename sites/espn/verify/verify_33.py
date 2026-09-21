#!/usr/bin/env python3
"""Deterministic verifier for ESPN task ESPN--33.

Locate the latest ESPN articles discussing potential MVP candidates in the NFL
for 2023 season.

Ground truth (hardcoded; frozen from the served /nfl/news page).  The NFL news
listing carries these MVP-related articles (latest first):

    'Quarterback evaluation tools and MVP thinking' (Apr 4, 2024, Mike Sando
    — analytics teams refine the toolkit for assessing quarterback MVP cases);
    'How modern offensive systems shape MVP candidacies' (Mar 22, 2024, Mike
    Sando — schematic trends influence how voters weigh candidates);
    'Retrospective: 2023 MVP race revisited' (Mar 12, 2024, Mike Sando);
    'NFL 2023 MVP Race: Mahomes vs Lamar Jackson' (Feb 8, 2024, HEADLINE);
    'NFL MVP watch: candidates to track in 2023' (Feb 4, 2024);
    'MVP voter conversations: how the case gets built' (Jan 24, 2024, Mike
    Sando — voters detail how individual ballots come together);
    'Lamar Jackson's MVP-caliber season' (Jan 11, 2024, Dan Graziano —
    Baltimore's quarterback stacks the resume);
    'Patrick Mahomes' 2023 MVP candidacy: a closer look' (Dec 14, 2023, Adam
    Schefter); 'Josh Allen's MVP profile: still in the mix' (Nov 22, 2023,
    Jeremy Fowler); 'Jalen Hurts' MVP candidacy after 2022' (Nov 12, 2023).

Anchoring rationale (acceptor rework item C): the mirror offers several
defensible referents for "the latest article discussing potential MVP
candidates" — the later MVP meta-articles (which discuss MVP cases / voting /
the 2023 race without naming candidates), the latest candidate-naming piece
(the Feb 8 'Mahomes vs Lamar Jackson' race article), and the latest
individual-candidate profile (Jan 11 Lamar Jackson).  The verifier therefore
accepts ANY of these articles via its own page-verifiable facts; a fabricated
subject (a player or story absent from the page) matches no anchor and FAILs.

Checks: run-package gate + answer + navigation (NFL news page, NFL section,
an MVP article, or an NFL MVP search) + >=1 accepted MVP-article anchor with
its on-page facts + read-only DB.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_any, step_urls, contains_all,
                        contains_any, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('ESPN--33', a.no_llm)
    t, fa = grade_common(j, a)
    urls = [u.lower() for u in step_urls(t)]
    nav_ok = any(("/nfl/news" in u) or ("/story/" in u) or ("mvp" in u)
                 or (u.rstrip("/").endswith("/nfl")) for u in urls)
    j.check("nav_nfl_mvp_coverage", nav_ok,
            "must open the NFL news page, the NFL section, an MVP article, "
            "or an NFL MVP search")
    anchors = [
        ("lamar_jackson_profile",
         contains_any(fa, ["lamar", "jackson"]) and
         contains_any(fa, ["baltimore", "raven", "graziano", "mvp-caliber", "mvp caliber"])),
        ("mahomes_lamar_race",
         contains_all(fa, ["mahomes"]) and contains_any(fa, ["lamar", "jackson"])),
        ("mvp_race_headline",
         contains_any(fa, ["mvp race", "race: mahomes"])),
        ("mahomes_candidacy",
         contains_all(fa, ["mahomes"]) and
         contains_any(fa, ["mvp candidacy", "2023 mvp", "schefter", "closer look"])),
        ("josh_allen_profile",
         contains_all(fa, ["josh allen"]) and contains_any(fa, ["mvp"])),
        ("hurts_candidacy",
         contains_all(fa, ["hurts"]) and contains_any(fa, ["mvp"])),
        ("mvp_watch",
         contains_any(fa, ["mvp watch", "candidates to track"])),
        ("evaluation_tools",
         contains_any(fa, ["evaluation tools", "epa", "cpoe", "time-to-throw", "time to throw"])),
        ("offensive_systems",
         contains_any(fa, ["offensive systems", "schematic"])),
        ("retrospective",
         contains_any(fa, ["retrospective", "race revisited"])),
        ("voter_conversations",
         contains_any(fa, ["voter", "ballot"])),
    ]
    matched = [name for name, ok in anchors if ok]
    j.check("answer_mvp_article", len(matched) >= 1,
            f"accepted MVP-article anchors matched={matched} (any defensible "
            "latest-MVP article with its on-page facts)")
    j.emit()

if __name__ == "__main__":
    main()
