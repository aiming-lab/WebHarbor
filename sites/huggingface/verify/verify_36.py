#!/usr/bin/env python3
"""Deterministic verifier for Hugging Face task Huggingface--36.

Task: Summarize all the payment plans and their advantages in huggingface pricing.

Ground truth (hardcoded; read off the served mirror pages with a real Chromium
during the reviewer audit — reports/huggingface/audit/; the catalog is fixed
by the seed DB and the mirror pins its clock to 2026-04-25, so no wall-clock
or upstream content is involved):
    /pricing lists three plans: HF Hub (Free forever — unlimited public
    models/datasets/Spaces, community support, free-tier Inference API,
    Git-based version control with LFS, CPU Spaces at no cost); PRO Account
    ($9 per month — ZeroGPU priority quota, private models and datasets with
    unlimited storage, early access to new Hub features, PRO badge, higher
    Inference API rate limits, PRO-only Spaces); Enterprise Hub ($20 per
    user/month — SSO/SAML and audit logs, SOC2 Type II, private Spaces with
    dedicated hardware, resource groups and RBAC, dedicated support with
    SLAs, custom inference regions, bring-your-own-cloud deployments).
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
    j = Judge('Huggingface--36', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_pricing_page", navigated_to(t, "/pricing"), "the pricing page")
    j.check("answer_free_plan",
            contains_any(fa, ["free", "hf hub"]) and contains_any(fa, ["public models",
            "public datasets", "cpu spaces", "community support"]),
            f"final={fa[:240]!r}")
    j.check("answer_pro_plan_9",
            contains_any(fa, ["pro"]) and contains_any(fa, ["$9", "9/month",
            "9 per month", "usd 9", "9 a month"]),
            f"final={fa[:240]!r}")
    j.check("answer_enterprise_plan_20",
            "enterprise" in fa.lower() and contains_any(fa, ["$20", "20/user",
            "20 per user", "usd 20", "$20/user", "20 a user"]),
            f"final={fa[:240]!r}")
    feats = count_named(fa, ["zerogpu", "private models", "private datasets",
                             "early access", "pro badge", "rate limit", "pro-only",
                             "sso", "saml", "soc2", "audit log", "dedicated hardware",
                             "bring-your-own-cloud", "bring your own cloud",
                             "custom inference region", "cpu spaces", "unlimited public"])
    j.check("answer_plan_advantages", feats >= 4,
            f"feature_hits={feats}; final={fa[:300]!r}")

    j.emit()


if __name__ == "__main__":
    main()
