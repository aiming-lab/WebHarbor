#!/usr/bin/env python3
"""Verifier for Kaggle--3 (stateful).

Find the 'Credit Card Fraud Transactions' dataset (slug credit-card-fraud-transactions) and
download it. Ground truth (after-state): the dataset's download counter is incremented vs the
seed (the /datasets/<slug>/download route bumps it). A no-op agent leaves it unchanged -> FAIL.

Checks: nav dataset + download route | DB after: downloads(after) > downloads(seed).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, dataset_downloads, load_run, navigated_to, origin_ok,
                        parse_args, resolve_db, run_complete, shot_at, shot_distinct,
                        shot_final)

SLUG = "credit-card-fraud-transactions"

def main():
    a = parse_args()
    j = Judge('Kaggle--3', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_dataset", navigated_to(t, f"/datasets/{SLUG}"), "opened the Credit Card Fraud dataset")
    # The download route is a CSRF-protected POST that 302-redirects back to the detail
    # page, so a browser agent may not record /download as its own step. The download
    # counter increment (below) is the authoritative, fail-closed proof that the download
    # action ran, and the screenshot binding proves the detail page was really rendered.
    before = dataset_downloads(init, SLUG)
    now = dataset_downloads(after, SLUG)
    j.check("db_available", before is not None and now is not None, f"seed={before} after={now}")
    j.check("db_download_incremented", before is not None and now is not None and now == before + 1,
            f"downloads seed={before} after={now}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/datasets/credit-card-fraud-transactions")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    j.emit()

if __name__ == "__main__":
    main()
