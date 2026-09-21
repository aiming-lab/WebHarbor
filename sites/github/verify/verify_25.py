#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--25.

'virtual reality' repo updated in the last 10 days with 200+ stars; objective.

Ground truth is hardcoded here and nowhere in tasks.jsonl; it was read off the
served pages of the running mirror container (all "last N days" filters anchor
to the site's frozen date 2024-05-15).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_repo,
                        visited_repo_any, search_url_with, step_urls, decoded,
                        contains_all, contains_any, mentions_repo, mentions_any_repo,
                        has_number, counts, figure_mentioned, mentions_date, Judge,
                        parse_args)

# Qualifying set served by /search?q=virtual reality
# updated:>2024-05-05 stars:>=200.
QUALIFIERS = {
    "vrlab/webvr-framework": ["webvr", "webxr", "immersive", "browser"],
    "vr-stream/vr-streaming-server": ["streaming", "wifi", "quest", "pico"],
    "vr-tools/vr-scene-editor": ["editor", "scenes", "content creation"],
    "mr-pals/mixed-reality-toolkit-2": ["mixed reality", "overlay", "digital content"],
    "unreal-vr/unreal-vr-template-archive": ["unreal", "template", "ue4"],
    "avp-pals/apple-vision-pro-sdk": ["vision pro", "visionos", "sdk"],
    "vr-game/virtual-reality-fps-game": ["fps", "unity", "quest"],
    "social-vr/social-vr-meetup": ["social", "avatar", "voice chat"],
    "aframe-pals/aframe-component-pack": ["a-frame", "aframe", "components"],
    "webvr-helpers/a-frame-extras-3d": ["a-frame", "aframe", "3d"],
    "vr-train/vr-medical-training": ["medical", "surgical", "training"],
    "vr-godot/godot-xr-helpers": ["godot", "xr", "games"],
    "vr-edu/vr-classroom-educator": ["classroom", "lessons", "education"],
    "pico-pals/pico-vr-helpers": ["pico", "headset", "unity"],
}

def main():
    a = parse_args()
    j = Judge('GitHub--25', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["virtual reality"]) or search_url_with(t, ["vr"])
           or visited_repo_any(t, list(QUALIFIERS)))
    j.check("nav_vr_search_or_repo", nav, "VR search or a qualifying repo page")
    named = mentions_any_repo(fa, list(QUALIFIERS))
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        j.check("answer_states_objective", contains_any(fa, QUALIFIERS[named]),
                f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
