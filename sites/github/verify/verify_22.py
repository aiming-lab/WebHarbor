#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--22.

NLP-in-Ruby repo updated within the last week.

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

# Qualifying set served by /search?q=natural language processing
# language:ruby updated:>2024-05-08.
QUALIFIERS = [
    "ruby-nlp/rnlp", "linguist-rb/rb-linguist", "rb-text/tokenizer-rb-classic",
    "ruby-sent/ruby-sentiment-rb", "ruby-tokenize/ruby-tokenizer-pro",
    "rb-vec/ruby-word-vectors", "ruby-ner/ruby-named-entity-rb",
    "ruby-stem/ruby-stemmer-snowball", "rb-corpus/ruby-corpus-loader",
    "ruby-lemma/ruby-lemmatizer-rb",
]

def main():
    a = parse_args()
    j = Judge('GitHub--22', a.no_llm)
    t, fa = grade_common(j, a)

    nav = ((search_url_with(t, ["ruby"]) and
            (search_url_with(t, ["nlp"]) or search_url_with(t, ["natural language"])))
           or visited_repo_any(t, QUALIFIERS))
    j.check("nav_ruby_nlp_search_or_repo", nav,
            "ruby NLP search with an updated constraint, or a qualifying repo page")
    named = mentions_any_repo(fa, QUALIFIERS)
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
