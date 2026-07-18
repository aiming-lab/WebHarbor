#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--3.

Open the climate and nature playlist, name one talk recorded at the TED
Countdown Summit 2025.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav climate-nature-conservation playlist | answer names one of the summit talks in that playlist
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

# The TED Countdown Summit 2025 talks that sit in the climate-nature-conservation
# playlist (titles + speakers accepted). Ground truth frozen from ted.db.
CANDIDATES = [
    "Conservation: a love story", "Elsaphan Njora",
    "A cheat sheet for accelerating clean energy", "Kimiko Hirata",
    "How to make transportation quieter, cleaner and cheaper", "Doreen Orishaba",
    "What China can teach the world about scaling clean energy", "Yin Yu",
    "The controversial climate tool funding real change", "Sandeep Roy Choudhury",
]

def main():
    a = parse_args()
    j = Judge('TED--3', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_climate_playlist", navigated_to(t, "playlists/climate-nature-conservation"),
            f"navigated={navigated_to(t, 'playlists/climate-nature-conservation')}")
    j.check("answer_names_summit_talk", contains_any(fa, CANDIDATES), f"final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
