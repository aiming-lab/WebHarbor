#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--17.

C++ project updated in the last week with 500+ stars; main purpose.

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

# Qualifying set served by /search?q=language:c++ updated:>2024-05-08 stars:>=500.
QUALIFIERS = {
    "electron/electron": ["desktop", "cross-platform", "javascript", "html", "css"],
    "imgproc/opencv-next": ["computer vision", "image processing", "vision"],
    "microsoft/terminal": ["terminal", "windows", "console"],
    "cpp-systems/fast-json-cpp": ["json", "parser"],
    "tensorflow/serving": ["serving", "machine learning", "models"],
    "engine-cpp/voxel-game-engine-cpp": ["game engine", "voxel", "vulkan", "ecs"],
    "cppdev/imgui-plus": ["imgui", "gui", "widgets", "debug"],
    "graphics-cpp/pbr-renderer-cpp": ["renderer", "path tracing", "vulkan"],
    "hft-cpp/low-latency-trading-cpp": ["trading", "order book", "hft", "lock-free"],
    "db-cpp/embedded-cpp-db": ["database", "storage engine", "embedded"],
    "btc-classic/bitcoin-core-helpers": ["bitcoin", "json-rpc", "blockchain"],
    "netsec-pals/cybersecurity-network-monitor": ["network", "packet", "monitor", "security"],
    "qsim-fast/quantum-state-simulator": ["quantum", "simulator", "gpu"],
    "distributed-cpp/distributed-consensus-cpp": ["distributed", "raft", "consensus"],
    "gui-cpp/imgui-flexi": ["gui", "ui", "docking"],
    "audio-cpp/realtime-audio-pipeline": ["audio", "dsp", "latency"],
    "unreal-vr/unreal-vr-template-archive": ["unreal", "vr", "template"],
    "cxx-game/entt-extras": ["entt", "entity", "ecs", "gamedev"],
    "robot-cpp/ros2-cpp-helpers": ["ros", "robotics", "sensor"],
    "embedded-cpp/mcu-firmware-framework": ["firmware", "microcontroller", "embedded"],
    "compiler-cpp/mini-cpp-compiler": ["compiler", "llvm"],
    "chem-quantum/quantum-chemistry-solver": ["chemistry", "dft", "electronic structure"],
}

def main():
    a = parse_args()
    j = Judge('GitHub--17', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["c++"]) or search_url_with(t, ["cpp"])
           or visited_repo_any(t, list(QUALIFIERS)))
    j.check("nav_cpp_search_or_repo", nav, "c++ search or a qualifying repo page")
    named = mentions_any_repo(fa, list(QUALIFIERS))
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        j.check("answer_describes_purpose", contains_any(fa, QUALIFIERS[named]),
                f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
