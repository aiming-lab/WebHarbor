#!/usr/bin/env python3
"""Deterministic verifier for ArXiv task ArXiv--40.

Task: "How many articles are there on each of the three most recent announce
days in the Solar and Stellar Astrophysics section of ArXiv. Choose one at
random and answer its title and when the first version was uploaded?"

The astro-ph.SR listing's three most recent announce days are 2026-04-28
(3 entries), 2026-04-27 (2), 2026-04-26 (3); the next (older) group is
2026-04-09 (7 entries). All 15 titles and their first-version (v1) upload
dates — as shown on the /abs pages — are hardcoded below.

Checks (deterministic):
  nav:    an astro-ph.SR listing URL or the chosen paper's /abs page
  answer: per-day counts 3 and 2 for the three most recent days; any April-2026
          day label the answer states must be one of the listing's real groups
          (26/27/28/9 Apr 2026) — hallucinated labels (e.g. 24 or 23 Apr) FAIL;
          a labelled answer must carry all three recent day dates, an unlabelled
          "3, 2 and 3 respectively" answer is accepted; the chosen paper's title
          and its first-version date must both appear.
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, step_urls, final_answer, has_number,
                        has_date, dates_in, paper_mentioned, navigated_to,
                        Judge, parse_args)

# (arxiv_id, title, first-version date)
PAPERS = [
    ("2604.89300", "A new stellar flare catalog from TESS", "2026-04-28"),
    ("2604.58997", "Solar wind modelling with MHD", "2026-04-28"),
    ("2604.23617", "Magnetic reconnection in solar coronal loops", "2026-04-28"),
    ("2604.78565", "Magnetic activity in M dwarfs", "2026-04-27"),
    ("2604.10718", "Asteroseismology of red giants in the Milky Way", "2026-04-27"),
    ("2604.73769", "Solar energetic particle events in Cycle 25", "2026-04-26"),
    ("2604.66789", "Binary stellar evolution with rotation", "2026-04-26"),
    ("2604.08081", "Stellar winds of hot massive stars", "2026-04-26"),
    ("2604.08422", "Expansion kinematics of young clusters", "2026-04-09"),
    ("2604.08387", "Searching for Ultracool Dwarfs in Early-Type Spectra", "2026-04-09"),
    ("2604.08379", "What you see is not necessarily what you get", "2026-04-09"),
    ("2604.08020", "Chromospheric turbulence as a regulator of stellar spin-down", "2026-04-09"),
    ("2604.07976", "The puzzling story of flare inactive ultracool dwarfs", "2026-04-09"),
    ("2604.07938", "eROSITA's cool star population explained", "2026-04-09"),
    ("2604.07932", "Candidate Microlensing Brown Dwarfs in the K2 mission", "2026-04-09"),
]
# The only April-2026 dates a faithful answer may state: the four real groups.
ALLOWED_APRIL_DATES = {"2026-04-28", "2026-04-27", "2026-04-26", "2026-04-09"}


def main():
    a = parse_args()
    j = Judge("ArXiv--40", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    urls = [u.lower() for u in step_urls(t)]
    matched = next((p for p in PAPERS if paper_mentioned(fa, p[0], p[1])), None)
    nav_ok = (any("astro-ph.sr" in u for u in urls)
              or (matched and navigated_to(t, f"/abs/{matched[0]}")))
    j.check("nav_astro_sr", nav_ok,
            f"urls={[u for u in urls if 'astro' in u][:4]}")

    april_list = [d for d in dates_in(fa) if d.startswith("2026-04-")]
    if matched and matched[2] in april_list:
        april_list.remove(matched[2])  # the chosen paper's v1 date is not a day label
    day_labels = set(april_list)
    j.check("answer_no_false_day_labels",
            day_labels <= ALLOWED_APRIL_DATES,
            f"day_labels={sorted(day_labels)} final={fa[:260]!r}")
    labelled = bool(day_labels & {"2026-04-28", "2026-04-27", "2026-04-26"})
    if labelled:
        j.check("answer_three_day_dates",
                {"2026-04-28", "2026-04-27", "2026-04-26"} <= day_labels,
                f"day_labels={sorted(day_labels)} final={fa[:260]!r}")
    j.check("answer_day_counts_3_and_2",
            has_number(fa, 3) and has_number(fa, 2),
            f"final={fa[:260]!r}")
    j.check("answer_names_chosen_paper", matched is not None,
            f"final={fa[:260]!r}")
    if matched is None:
        j.emit()
    j.check("answer_first_version_date",
            has_date(fa, matched[2]),
            f"need={matched[2]} final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
