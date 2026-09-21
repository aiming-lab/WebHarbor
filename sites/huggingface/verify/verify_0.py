#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--0.

Task: Find a pre-trained natural language processing model on Hugging Face that can perform sentiment analysis, and make sure the model's last update is within March 2023.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    Sentiment-analysis (text-classification) models whose updated_at falls in
    March 2023 — exactly the rows of /models?task=text-classification&updated_month=2023-03:
      nlptown/bert-base-multilingual-uncased-sentiment  (Mar 28, 2023)
      cmarkea/distilcamembert-base-sentiment             (Mar 22, 2023)
      finiteautomata/bertweet-base-sentiment-analysis    (Mar 22, 2023)
      cardiffnlp/twitter-xlm-roberta-base-sentiment      (Mar 15, 2023)
      j-hartmann/sentiment-roberta-large-english-3-classes (Mar 11, 2023)
      mrm8488/distilroberta-finetuned-financial-news-sentiment (Mar 08, 2023)
      savasy/bert-base-turkish-sentiment-cased           (Mar 05, 2023)
      siebert/sentiment-roberta-large-english           (Mar 05, 2023)
    The answer must name one of these and carry its March-2023 update date.
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts. Input/Output: verify_lib.parse_args / Judge.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, listing_step,
                        visited_model, visited_dataset, visited_space,
                        visited_model_slugs, contains_all, contains_any,
                        big_number_in, decimal_in, date_token_in, count_named,
                        Judge, parse_args)



def main():
    a = parse_args()
    j = Judge('Huggingface--0', a.no_llm)
    t, fa = grade_common(j, a)
    CANDIDATES = {
        "bert-base-multilingual-uncased-sentiment": (3, 28, 2023),
        "distilcamembert-base-sentiment": (3, 22, 2023),
        "bertweet-base-sentiment-analysis": (3, 22, 2023),
        "twitter-xlm-roberta-base-sentiment": (3, 15, 2023),
        "sentiment-roberta-large-english-3-classes": (3, 11, 2023),
        "distilroberta-finetuned-financial-news-sentiment": (3, 8, 2023),
        "bert-base-turkish-sentiment-cased": (3, 5, 2023),
        "sentiment-roberta-large-english": (3, 5, 2023),
    }
    urls = __import__('verify_lib').step_urls(t)
    j.check("nav_sentiment_listing_or_page",
            navigated_any(t, ["sentiment"]) or listing_step(t, ["task=text-classification"]),
            f"urls={[u for u in urls if 'sentiment' in u.lower() or 'text-classification' in u.lower()][:4]}")
    named = [(name, d) for name, d in CANDIDATES.items() if name in fa.lower()]
    j.check("answer_names_march_2023_sentiment_model", bool(named),
            f"final={fa[:200]!r}")
    if named:
        name, (mo, day, yr) = named[0]
        j.check("answer_sentiment_task", "sentiment" in fa.lower(), f"final={fa[:120]!r}")
        j.check("answer_march_2023_date",
                date_token_in(fa, "Mar", day, yr) or ("march" in fa.lower() and str(yr) in fa),
                f"expected ~Mar {day}, {yr}; final={fa[:200]!r}")

    j.emit()


if __name__ == "__main__":
    main()
