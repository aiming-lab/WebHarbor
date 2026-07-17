#!/usr/bin/env python3
"""Craigslist--14: electronics — the Dell 27 inch USB-C monitor in Sunnyvale; report its resolution
and ports. GT (id 9): resolution 2560x1440; ports USB-C, HDMI, DP."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, opened_listing, contains_any, contains_all,
                        llm_text_match, Judge, parse_args)
def main():
    a = parse_args(); j = Judge('Craigslist--14', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    j.check("nav_listing", opened_listing(t, 9), "expected the Dell 27\" USB-C monitor (id 9)")
    j.check("answer_res", contains_any(fa, ["2560x1440", "2560 x 1440", "1440p", "qhd"]),
            f"expected resolution 2560x1440; final={fa!r}")
    j.check("answer_ports", contains_all(fa, ["usb-c"]) and contains_any(fa, ["hdmi", "dp", "displayport"]),
            "expected ports USB-C / HDMI / DP")
    ok, ev = llm_text_match(fa, "resolution 2560x1440; ports USB-C, HDMI, DP",
                            "Report the monitor's resolution and ports.")
    j.check("answer_consistent", ok, ev, llm=True)
    j.emit()
if __name__ == "__main__":
    main()
