#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--9.

Repo created in the last week with 50+ stars: purpose and language.

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

# Qualifying set served by /search?q=created:>2024-05-08 stars:>=50&sort=stars.
QUALIFIERS = {
    "gaming-fresh/pixel-art-editor-fresh": ("typescript", ["pixel art", "editor"]),
    "may24-js/oxlint-js": ("javascript", ["lint", "linter", "oxlint"]),
    "ext-fresh/browser-tab-saver": ("javascript", ["tab", "sessions", "extension"]),
    "design-fresh/figma-tokens-cli": ("typescript", ["figma", "design tokens", "cli"]),
    "docs-fresh/devops-handbook-2024": ("markdown", ["devops", "handbook", "documentation"]),
    "webapp-fresh/task-board-app": ("typescript", ["kanban", "task board", "drag"]),
    "cli-fresh/just-launched-cli": ("go", ["git worktrees", "worktree", "cli"]),
    "fresh-code/quick-utility": ("typescript", ["utility"]),
    "week-deploy/kubectl-quick-debug": ("go", ["kubectl", "debug"]),
    "lan-newdev/ws-relay": ("go", ["websocket", "relay"]),
    "framework-fresh/mini-web-framework": ("python", ["web framework", "flask", "api"]),
    "pri-launch/prompt-templater": ("python", ["prompt", "llm", "templating"]),
    "ten-day/dns-cache-mini": ("rust", ["dns", "cache"]),
    "finance-fresh/budget-cli-fresh": ("rust", ["budget", "finance", "cli"]),
    "weekly-dev/new-fresh-tool": ("go", ["productivity", "tool"]),
    "premiere-week/audio-cli-converter": ("rust", ["audio", "converter"]),
    "lib-fresh/micro-orm-rs": ("rust", ["orm"]),
    "just-up/oauth-mock-server": ("go", ["oauth", "mock"]),
}

def main():
    a = parse_args()
    j = Judge('GitHub--9', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["created"]) or visited_repo_any(t, list(QUALIFIERS)))
    j.check("nav_created_search_or_repo", nav,
            "created-constrained search, or a qualifying repo page")
    named = mentions_any_repo(fa, list(QUALIFIERS))
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        lang, toks = QUALIFIERS[named]
        j.check("answer_states_language", contains_any(fa, [lang]), f"expected {lang!r}")
        j.check("answer_describes_purpose", contains_any(fa, toks), f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
