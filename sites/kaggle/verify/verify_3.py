#!/usr/bin/env python3
"""Verifier for Kaggle--3 (stateful).

Find the 'Credit Card Fraud Transactions' dataset (slug credit-card-fraud-transactions) and
download it. Ground truth (after-state): the dataset's download counter is incremented vs the
seed (the /datasets/<slug>/download route bumps it). A no-op agent leaves it unchanged -> FAIL.

Checks: nav dataset + download route | DB after: downloads(after) > downloads(seed).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, dataset_downloads,
                        Judge, parse_args)

SLUG = "credit-card-fraud-transactions"

def main():
    a = parse_args()
    j = Judge('Kaggle--3', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_dataset", navigated_to(t, f"/datasets/{SLUG}"), "opened the Credit Card Fraud dataset")
    # The download route 302-redirects back to the detail page, so a browser agent may not
    # record /download as its own step. The download counter increment (below) is the
    # authoritative, fail-closed proof that the download action ran.
    before = dataset_downloads(init, SLUG)
    now = dataset_downloads(after, SLUG)
    j.check("db_available", before is not None and now is not None, f"seed={before} after={now}")
    j.check("db_download_incremented", before is not None and now is not None and now > before,
            f"downloads seed={before} after={now}")
    j.emit()

if __name__ == "__main__":
    main()
