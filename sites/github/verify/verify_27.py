#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--27.

Ruby repo updated in the past 3 days with 1000+ stars.

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

# Qualifying set served by /search?q=language:ruby
# updated:>2024-05-12 stars:>=1000.
QUALIFIERS = [
    "ruby-core/fast-ruby", "sidekiq-next/sidekiq-plus", "hanami/hanami-rb",
    "rb-graphql/graphql-rb-mature", "rails-pals/rails-actiontext-extras",
    "sinatra-pals/sinatra-streaming-helpers", "hanami-pals/hanami-cli-plus",
    "sidekiq-pals/sidekiq-pro-helpers", "cap-pals/capistrano-docker-extras",
    "rspec-pals/rspec-mocks-extra", "gem-pals/gem-packaging-tools",
]

def main():
    a = parse_args()
    j = Judge('GitHub--27', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["ruby"]) or visited_repo_any(t, QUALIFIERS))
    j.check("nav_ruby_search_or_repo", nav, "ruby search or a qualifying repo page")
    named = mentions_any_repo(fa, QUALIFIERS)
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
