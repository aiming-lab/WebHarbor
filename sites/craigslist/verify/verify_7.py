#!/usr/bin/env python3
"""Craigslist--7: log in as alice, open Alice's messages, identify the showing times the leasing
office offered for the Berkeley studio. GT (pre-seeded inbound message on listing 21): "The
Berkeley studio can be shown Wednesday at 5:30pm or Thursday at noon." """
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, navigated_to, contains_all,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--7', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_messages", navigated_to(t, "/messages"), "expected Alice's messages")
    j.check("answer_times", contains_all(fa, ["wednesday", "thursday"]),
            f"expected both showing times (Wed 5:30pm / Thu noon); final={fa!r}")
    ok, ev = llm_text_match(fa, "Wednesday at 5:30pm or Thursday at noon",
                            "What showing times did the leasing office offer for the Berkeley studio?")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
