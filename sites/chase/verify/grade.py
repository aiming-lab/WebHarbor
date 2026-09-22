"""Shared deterministic CHASE task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED in answers.py (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / money / tokens /
     phones / clock hours / dates, negation-aware, with bounded word forms)
  4. DB after-state: read-only tasks leave every table unchanged; the eight
     stateful tasks (21-28) and the public application task (29) must produce
     exactly the requested rows/fields and preserve the rest. Tasks 27/28 are
     the re-anchored stateful semantics: T27 must complete the actual $150
     card payment (a visit-only or ask-only run fails on the missing payment
     rows); T28 must actually cancel the scheduled savings autosave transfer.
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, scalar, preserved,
    new_rows, tables_unchanged, navigated_path, navigated_prefix,
    navigated_query, contains_count, contains_money, affirm_number,
    affirm_money, affirm_score, affirm_hour, contains_phone, affirms,
    affirms_any, contains_any, contains_number, norm, final_answer,
    step_text, contains_date_iso_or_md, contains_date_forms,
)
import answers as A

STATEFUL = {21, 22, 23, 24, 25, 26, 27, 28, 29}

# URL substring each task's evidence screenshot must be bound to (the page the
# task depends on; anti "answer without opening the page" shortcut).
SHOT_ANCHORS = {
    0: "card/sapphire-reserve", 1: "category/travel", 2: "compare",
    3: "card/ink-business-cash", 4: "checking/total-checking",
    5: "/checking", 6: "savings/chase-savings", 7: "/cds",
    8: "mortgage/rates", 9: "mortgage/calculator", 10: "auto/rates",
    11: "auto/calculator", 12: "locator/branch/300", 13: "locator/branch/49",
    14: "article/what-happens-when-you-pay-off-debt", 15: "article/747-credit-score",
    16: "customer-service", 17: "/account", 18: "transactions",
    19: "statements", 20: "credit-journey", 21: "transfer",
    22: "transfers", 23: "/account/pay/", 24: "autopay", 25: "alerts",
    26: "rewards", 27: "/account/pay/", 28: "transfers",
    29: "doordash-rewards-mastercard",
}


def _money_pair(fa, pair):
    """A (label, value) waiver condition: label affirmed + value present."""
    return affirms(fa, pair[0]) and contains_money(fa, pair[1])


def _row_matches(row, **want):
    return all(row.get(k) == v for k, v in want.items())


def grade(number):
    args = parse_args()
    j = Judge(f"Chase--{number}")
    t = load_run(args.run_dir)
    fa = final_answer(t)
    init_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    b, a = rows(init_db), rows(after_db)
    j.bind_run(t, require_answer=True, shot_url=SHOT_ANCHORS.get(number))

    if number not in STATEFUL:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            changed = tables_unchanged(init_db, after_db)
            j.check("db_unchanged", changed == [],
                    f"changed tables: {changed}" if changed else "all tables unchanged")

    # ---------------- read-only public catalog tasks ----------------
    if number == 0:
        j.check("visited_sapphire_reserve", navigated_path(t, "/credit-cards/card/sapphire-reserve"),
                "Sapphire Reserve detail page")
        j.check("answer_fee", affirm_money(fa, A.T0_FEE), fa)
        j.check("answer_apr_low", affirms_any(fa, [A.T0_APR_LOW, "19.49%"]), fa)
        j.check("answer_apr_high", affirms_any(fa, [A.T0_APR_HIGH, "27.99%"]), fa)

    elif number == 1:
        j.check("visited_travel_category", navigated_path(t, "/credit-cards/category/travel"),
                "travel cards category page")
        j.check("answer_count", contains_count(fa, A.T1_COUNT), fa)
        for token_a, token_b in A.T1_FREE_TOKENS:
            j.check(f"answer_free_{token_b.lower()}",
                    affirms(fa, token_a) and affirms(fa, token_b), fa)
        j.check("answer_free_fee", affirms_any(fa, ["$0", "no annual fee", "0 annual fee"]), fa)

    elif number == 2:
        j.check("visited_compare", navigated_query(t, "/credit-cards/compare",
                                                   cards="freedom-flex,freedom-unlimited"),
                "comparison page with both cards")
        j.check("answer_unlimited_rate", affirm_score(fa, A.T2_UNLIMITED_RATE), fa)
        j.check("answer_flex_quarterly", affirms_any(fa, list(A.T2_FLEX_QUARTERLY)), fa)
        j.check("answer_flex_flat", affirms(fa, A.T2_FLEX_FLAT), fa)

    elif number == 3:
        j.check("visited_ink_cash", navigated_path(t, "/credit-cards/card/ink-business-cash"),
                "Ink Business Cash detail page")
        for tok in A.T3_5PCT_CATS:
            j.check(f"answer_cat_{tok.split()[0]}", affirms(fa, tok), fa)
        j.check("answer_phone_services", affirms(fa, "phone"), fa)
        j.check("answer_cap", affirm_money(fa, A.T3_CAP) or contains_any(fa, ["25K", "25k"]),
                fa)
        j.check("answer_anniversary", affirms(fa, A.T3_ANNIVERSARY), fa)

    elif number == 4:
        j.check("visited_total_checking", navigated_path(t, "/checking/total-checking"),
                "Total Checking detail page")
        j.check("answer_fee", affirm_money(fa, A.T4_FEE), fa)
        ok = any(_money_pair(fa, w) for w in A.T4_WAIVERS)
        j.check("answer_one_waiver", ok, fa)

    elif number == 5:
        j.check("visited_students_tab", navigated_query(t, "/checking", tab="students"),
                "checking page filtered to Students & Kids")
        for name in A.T5_NAMES:
            j.check(f"answer_{name.split()[0].lower()}_{name.split()[1].lower()}",
                    affirms(fa, name), fa)
        for lo, hi in A.T5_RANGES:
            j.check(f"answer_age_{lo}_{hi}",
                    contains_number(fa, lo) and contains_number(fa, hi), fa)

    elif number == 6:
        j.check("visited_chase_savings", navigated_path(t, "/savings/chase-savings"),
                "Chase Savings detail page")
        j.check("answer_fee", affirm_money(fa, A.T6_FEE), fa)
        ok = False
        for label, value in A.T6_WAIVERS:
            if value is None:
                ok = ok or affirms(fa, label)
            else:
                ok = ok or (affirms(fa, label) and contains_money(fa, value))
        j.check("answer_one_waiver", ok, fa)

    elif number == 7:
        j.check("visited_cds", navigated_path(t, "/cds"), "CD rates page")
        j.check("answer_term", contains_number(fa, 12), fa)
        j.check("answer_apy", affirm_score(fa, A.T7_APY) or affirms_any(fa, ["3.5", "3.50", "3.5%", "3.50%"]), fa)
        j.check("answer_min", affirm_money(fa, A.T7_MIN), fa)

    elif number == 8:
        j.check("visited_mortgage_rates", navigated_path(t, "/mortgage/rates"),
                "mortgage rates page")
        j.check("answer_rate", affirm_score(fa, A.T8_RATE) or affirms_any(fa, ["6.75", "6.750", "6.75%", "6.750%"]), fa)
        j.check("answer_apr", affirms(fa, f"{A.T8_APR}%"), fa)
        j.check("answer_monthly", affirm_money(fa, A.T8_MONTHLY), fa)
        j.check("answer_zip", contains_number(fa, A.T8_ZIP), fa)

    elif number == 9:
        j.check("visited_calculator", navigated_path(t, "/mortgage/calculator"),
                "mortgage calculator (form + result)")
        j.check("answer_monthly", affirm_money(fa, A.T9_MONTHLY), fa)
        j.check("answer_total_interest", affirm_money(fa, A.T9_TOTAL_INTEREST), fa)

    elif number == 10:
        j.check("visited_auto_rates", navigated_path(t, "/auto/rates"), "auto rates page")
        j.check("answer_apr", affirm_score(fa, A.T10_APR) or affirms_any(fa, ["6.59", "6.59%"]), fa)
        j.check("answer_term", contains_number(fa, A.T10_TERM), fa)
        j.check("answer_payment", affirm_money(fa, A.T10_PAYMENT), fa)

    elif number == 11:
        j.check("visited_car_calc", navigated_path(t, "/auto/calculator"),
                "car payment calculator (form + result)")
        j.check("answer_monthly", affirm_money(fa, A.T11_MONTHLY), fa)
        j.check("answer_total", affirm_money(fa, A.T11_TOTAL), fa)

    elif number == 12:
        j.check("visited_locator_seattle", navigated_query(t, "/locator", q={"Seattle", "seattle"}),
                "locator searched for Seattle")
        j.check("visited_ballard", navigated_path(t, f"/locator/branch/{A.T12_BALLARD_ID}"),
                "Ballard branch detail page")
        j.check("answer_count", contains_count(fa, A.T12_COUNT), fa)
        j.check("answer_street", affirms(fa, "5511") and affirms(fa, "22nd Ave"), fa)
        j.check("answer_zip", affirms(fa, A.T12_BALLARD_ZIP), fa)
        j.check("answer_phone", contains_phone(fa, A.T12_BALLARD_PHONE), fa)

    elif number == 13:
        j.check("visited_locator_chicago", navigated_query(t, "/locator", q={"Chicago", "chicago"}),
                "locator searched for Chicago")
        j.check("visited_madison_halsted", navigated_path(t, f"/locator/branch/{A.T13_BRANCH_ID}"),
                "Madison and Halsted branch detail page")
        j.check("answer_street", affirms(fa, A.T13_ADDRESS_NUM) and affirms(fa, A.T13_ADDRESS_STREET), fa)
        j.check("answer_thursday", affirms(fa, "Thursday"), fa)
        h, m, mer = A.T13_THURSDAY_OPEN
        j.check("answer_open_time", affirm_hour(fa, h, m, mer), fa)
        h, m, mer = A.T13_THURSDAY_CLOSE
        j.check("answer_close_time", affirm_hour(fa, h, m, mer), fa)

    elif number == 14:
        j.check("visited_article", navigated_path(t, "/education/article/what-happens-when-you-pay-off-debt"),
                "pay-off-debt article page")
        ok = False
        for token, extras in A.T14_EFFECTS:
            if extras:
                ok = ok or (affirms(fa, token) and affirms_any(fa, list(extras)))
            else:
                ok = ok or affirms(fa, token)
        j.check("answer_one_effect", ok, fa)

    elif number == 15:
        j.check("visited_article", navigated_path(t, "/education/article/747-credit-score"),
                "747 credit score article")
        j.check("answer_band", affirms(fa, A.T15_BAND) or affirms(fa, A.T15_BAND_ALT), fa)
        j.check("answer_factor", affirms_any(fa, A.T15_FACTORS), fa)

    elif number == 16:
        j.check("visited_customer_service", navigated_path(t, "/customer-service"),
                "customer service page")
        j.check("answer_personal_phone", contains_phone(fa, A.T16_PERSONAL), fa)
        j.check("answer_home_lending_phone", contains_phone(fa, A.T16_HOME_LENDING), fa)

    # ---------------- authenticated read-only tasks ----------------
    elif number == 17:
        j.check("visited_dashboard", navigated_path(t, "/account"), "accounts dashboard")
        j.check("answer_checking", affirm_money(fa, A.T17_CHECKING), fa)
        j.check("answer_savings", affirm_money(fa, A.T17_SAVINGS), fa)

    elif number == 18:
        j.check("visited_txns_dining", navigated_query(t, "/account/transactions", category="dining"),
                "transactions page filtered to dining")
        j.check("answer_total", affirm_money(fa, A.T18_TOTAL), fa)
        j.check("answer_max_merchant", affirms(fa, A.T18_MAX_MERCHANT), fa)
        j.check("answer_max_amount", affirm_money(fa, A.T18_MAX_AMOUNT), fa)

    elif number == 19:
        j.check("visited_statements", navigated_path(t, "/account/statements"), "statements page")
        j.check("answer_period", affirms(fa, A.T19_PERIOD) or (affirms(fa, "September") and contains_number(fa, 2026)), fa)
        j.check("answer_balance", affirm_money(fa, A.T19_BALANCE), fa)
        j.check("answer_points", contains_number(fa, A.T19_POINTS), fa)
        j.check("answer_card_named", affirms(fa, "Ink Business"), fa)

    elif number == 20:
        j.check("visited_credit_journey", navigated_path(t, "/account/credit-journey"),
                "Credit Journey page")
        j.check("answer_score", contains_number(fa, A.T20_SCORE), fa)
        j.check("answer_band", affirms(fa, A.T20_BAND), fa)
        j.check("answer_delta", affirm_number(fa, A.T20_DELTA), fa)

    # ---------------- stateful tasks ----------------
    elif number == 21:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            additions = new_rows(b, a, "transfers")
            j.check("visited_transfer_form", navigated_path(t, "/account/transfer"),
                    "transfer form")
            j.check("visited_transfers_page", navigated_path(t, "/account/transfers"),
                    "transfers page (confirmation)")
            want = A.T21_NEW_TRANSFER
            j.check("exactly_one_new_transfer", len(additions) == 1,
                    f"new transfers: {[r.get('id') for r in additions]}")
            if len(additions) == 1:
                row = additions[0]
                for k, v in want.items():
                    j.check(f"transfer_{k}", row.get(k) == v,
                            f"{k}: {row.get(k)!r} vs {v!r}")
                for tok in A.T21_FROM_TOKENS:
                    j.check(f"transfer_from_label_{tok}", tok in (row.get("from_label") or ""), row.get("from_label"))
                for tok in A.T21_TO_TOKENS:
                    j.check(f"transfer_to_label_{tok}", tok in (row.get("to_label") or ""), row.get("to_label"))
            ok = preserved(b, a, additions={"transfers": [r["id"] for r in additions]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_amount", affirm_money(fa, A.T21_AMOUNT), fa)
        j.check("answer_scheduled", affirms(fa, "scheduled"), fa)
        j.check("answer_date", contains_date_iso_or_md(fa, A.T21_DATE), fa)

    elif number == 22:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_transfers_page", navigated_path(t, "/account/transfers"),
                    "transfers page")
            row_b = scalar(b, "transfers", id=A.T22_TRANSFER_ID)
            row_a = scalar(a, "transfers", id=A.T22_TRANSFER_ID)
            if row_b is None or row_a is None:
                j.check("target_transfer_exists", False,
                        f"seeded transfer id {A.T22_TRANSFER_ID} missing")
            else:
                j.check("was_scheduled", row_b.get("status") == "scheduled", row_b.get("status"))
                j.check("now_canceled", row_a.get("status") == "canceled", row_a.get("status"))
            ok = preserved(b, a, changes={"transfers": {A.T22_TRANSFER_ID: {"status"}}})
            j.check("other_state_preserved", ok, "only that one status cell changed")
        j.check("answer_canceled", affirms(fa, "cancel"), fa)
        j.check("answer_rule", affirm_money(fa, A.T22_AMOUNT) or affirms_any(fa, list(A.T22_CARD_TOKENS)), fa)

    elif number == 23:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_pay_form", navigated_prefix(t, "/account/pay/"), "pay-card form")
            j.check("visited_dashboard", navigated_path(t, "/account"), "dashboard (confirmation)")
            pays = new_rows(b, a, "card_payments")
            txns = new_rows(b, a, "transactions")
            j.check("exactly_one_payment", len(pays) == 1,
                    f"new card_payments: {[r.get('id') for r in pays]}")
            if len(pays) == 1:
                p = pays[0]
                j.check("payment_card_account", p.get("card_account_id") == A.T23_CARD_ID,
                        f"card_account_id: {p.get('card_account_id')}")
                j.check("payment_amount", p.get("amount") == A.T23_AMOUNT, f"amount: {p.get('amount')}")
                j.check("payment_date", p.get("date") == A.MIRROR_DATE, f"date: {p.get('date')}")
                j.check("payment_from_label", A.T23_FROM_TOKEN in (p.get("from_label") or ""),
                        p.get("from_label"))
            j.check("exactly_one_txn", len(txns) == 1 and txns[0].get("category") == "payment"
                    and txns[0].get("amount") == A.T23_AMOUNT,
                    f"new transactions: {[r.get('id') for r in txns]}")
            if len(txns) == 1:
                for tok in A.T23_TXN_DESC_TOKENS:
                    j.check(f"txn_desc_{tok.split()[0].lower()}", tok in (txns[0].get("description") or ""),
                            txns[0].get("description"))
            bank_b = scalar(b, "bank_accounts", id=A.T23_BANK_ID)
            bank_a = scalar(a, "bank_accounts", id=A.T23_BANK_ID)
            card_b = scalar(b, "card_accounts", id=A.T23_CARD_ID)
            card_a = scalar(a, "card_accounts", id=A.T23_CARD_ID)
            j.check("checking_before", bank_b is not None and abs((bank_b or {}).get("balance", 0) - A.T23_CHECKING_BEFORE) < 0.001,
                    (bank_b or {}).get("balance"))
            j.check("checking_after", bank_a is not None and abs((bank_a or {}).get("balance", 0) - A.T23_CHECKING_AFTER) < 0.001,
                    (bank_a or {}).get("balance"))
            j.check("card_before", card_b is not None and abs((card_b or {}).get("balance", 0) - A.T23_CARD_BEFORE) < 0.001,
                    (card_b or {}).get("balance"))
            j.check("card_after", card_a is not None and abs((card_a or {}).get("balance", 0) - A.T23_CARD_AFTER) < 0.001,
                    (card_a or {}).get("balance"))
            ok = preserved(
                b, a,
                additions={"card_payments": [r["id"] for r in pays],
                           "transactions": [r["id"] for r in txns]},
                changes={"bank_accounts": {A.T23_BANK_ID: {"balance"}},
                         "card_accounts": {A.T23_CARD_ID: {"balance"}}},
            )
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_new_balance", affirm_money(fa, A.T23_CARD_AFTER), fa)
        j.check("answer_amount", affirm_money(fa, A.T23_AMOUNT), fa)

    elif number == 24:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_autopay", navigated_path(t, "/account/autopay"),
                    "automatic payments page")
            row_b = scalar(b, "card_accounts", id=A.T24_CARD_ID)
            row_a = scalar(a, "card_accounts", id=A.T24_CARD_ID)
            if row_b is None or row_a is None:
                j.check("target_card_exists", False, f"card account {A.T24_CARD_ID} missing")
            else:
                j.check("was_autopay_on", row_b.get("autopay") in (True, 1), row_b.get("autopay"))
                j.check("now_autopay_off", row_a.get("autopay") in (False, 0), row_a.get("autopay"))
            ok = preserved(b, a, changes={"card_accounts": {A.T24_CARD_ID: {"autopay"}}})
            j.check("other_state_preserved", ok, "only that one flag changed")
        j.check("answer_off", affirms(fa, "off") or affirms(fa, "no longer"), fa)
        j.check("answer_card_named", affirms_any(fa, list(A.T24_CARD_TOKENS)), fa)

    elif number == 25:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_alerts", navigated_path(t, "/account/alerts"), "alerts page")
            adds = new_rows(b, a, "alerts")
            j.check("exactly_one_new_alert", len(adds) == 1,
                    f"new alerts: {[r.get('id') for r in adds]}")
            if len(adds) == 1:
                row = adds[0]
                for k, v in A.T25_ALERT.items():
                    j.check(f"alert_{k}", row.get(k) == v, f"{k}: {row.get(k)!r} vs {v!r}")
            ok = preserved(b, a, additions={"alerts": [r["id"] for r in adds]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_type", affirms(fa, "low balance"), fa)
        j.check("answer_threshold", affirm_money(fa, A.T25_ALERT["threshold"]), fa)
        j.check("answer_channel", affirms(fa, "mobile"), fa)

    elif number == 26:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_rewards", navigated_path(t, "/account/rewards"), "rewards page")
            reds = new_rows(b, a, "reward_redemptions")
            j.check("exactly_one_redemption", len(reds) == 1,
                    f"new redemptions: {[r.get('id') for r in reds]}")
            if len(reds) == 1:
                r0 = reds[0]
                j.check("redemption_card", r0.get("card_account_id") == A.T26_CARD_ID,
                        f"card_account_id: {r0.get('card_account_id')}")
                j.check("redemption_points", r0.get("points") == A.T26_POINTS,
                        f"points: {r0.get('points')}")
                j.check("redemption_value", abs((r0.get("value") or 0) - A.T26_VALUE) < 0.001,
                        f"value: {r0.get('value')}")
                j.check("redemption_type", r0.get("redemption_type") == "cash back",
                        f"type: {r0.get('redemption_type')!r}")
                j.check("redemption_date", r0.get("date") == A.MIRROR_DATE, f"date: {r0.get('date')}")
            row_b = scalar(b, "card_accounts", id=A.T26_CARD_ID)
            row_a = scalar(a, "card_accounts", id=A.T26_CARD_ID)
            if row_b is None or row_a is None:
                j.check("target_card_exists", False, f"card account {A.T26_CARD_ID} missing")
            else:
                j.check("points_before", row_b.get("points") == A.T26_POINTS_BEFORE, row_b.get("points"))
                j.check("points_after", row_a.get("points") == A.T26_POINTS_AFTER, row_a.get("points"))
            ok = preserved(
                b, a,
                additions={"reward_redemptions": [r["id"] for r in reds]},
                changes={"card_accounts": {A.T26_CARD_ID: {"points"}}},
            )
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_value", affirm_money(fa, A.T26_VALUE), fa)
        j.check("answer_points", contains_number(fa, A.T26_POINTS), fa)

    elif number == 27:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_dashboard", navigated_path(t, "/account"),
                    "accounts dashboard (compare card balances)")
            j.check("visited_pay_form", navigated_prefix(t, f"/account/pay/{A.T27_CARD_ID}"),
                    "pay-card form for the higher-balance card")
            pays = new_rows(b, a, "card_payments")
            txns = new_rows(b, a, "transactions")
            j.check("exactly_one_payment", len(pays) == 1,
                    f"new card_payments: {[r.get('id') for r in pays]}")
            if len(pays) == 1:
                p = pays[0]
                j.check("payment_card_account", p.get("card_account_id") == A.T27_CARD_ID,
                        f"card_account_id: {p.get('card_account_id')} (must be the higher-balance card)")
                j.check("payment_amount", p.get("amount") == A.T27_AMOUNT, f"amount: {p.get('amount')}")
                j.check("payment_date", p.get("date") == A.MIRROR_DATE, f"date: {p.get('date')}")
                j.check("payment_from_label", A.T27_FROM_TOKEN in (p.get("from_label") or ""),
                        p.get("from_label"))
            j.check("exactly_one_txn", len(txns) == 1 and txns[0].get("category") == "payment"
                    and txns[0].get("amount") == A.T27_AMOUNT,
                    f"new transactions: {[r.get('id') for r in txns]}")
            if len(txns) == 1:
                for tok in A.T27_TXN_DESC_TOKENS:
                    j.check(f"txn_desc_{tok.split()[0].lower()}", tok in (txns[0].get("description") or ""),
                            txns[0].get("description"))
            bank_b = scalar(b, "bank_accounts", id=A.T27_BANK_ID)
            bank_a = scalar(a, "bank_accounts", id=A.T27_BANK_ID)
            card_b = scalar(b, "card_accounts", id=A.T27_CARD_ID)
            card_a = scalar(a, "card_accounts", id=A.T27_CARD_ID)
            j.check("checking_before", bank_b is not None and abs((bank_b or {}).get("balance", 0) - A.T27_CHECKING_BEFORE) < 0.001,
                    (bank_b or {}).get("balance"))
            j.check("checking_after", bank_a is not None and abs((bank_a or {}).get("balance", 0) - A.T27_CHECKING_AFTER) < 0.001,
                    (bank_a or {}).get("balance"))
            j.check("card_before", card_b is not None and abs((card_b or {}).get("balance", 0) - A.T27_CARD_BEFORE) < 0.001,
                    (card_b or {}).get("balance"))
            j.check("card_after", card_a is not None and abs((card_a or {}).get("balance", 0) - A.T27_CARD_AFTER) < 0.001,
                    (card_a or {}).get("balance"))
            ok = preserved(
                b, a,
                additions={"card_payments": [r["id"] for r in pays],
                           "transactions": [r["id"] for r in txns]},
                changes={"bank_accounts": {A.T27_BANK_ID: {"balance"}},
                         "card_accounts": {A.T27_CARD_ID: {"balance"}}},
            )
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_card_named", affirms_any(fa, list(A.T27_CARD_TOKENS)), fa)
        j.check("answer_new_balance", affirm_money(fa, A.T27_CARD_AFTER), fa)
        j.check("answer_amount", affirm_money(fa, A.T27_AMOUNT), fa)

    elif number == 28:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_transfers_page", navigated_path(t, "/account/transfers"),
                    "transfers page")
            row_b = scalar(b, "transfers", id=A.T28_TRANSFER_ID)
            row_a = scalar(a, "transfers", id=A.T28_TRANSFER_ID)
            if row_b is None or row_a is None:
                j.check("target_transfer_exists", False,
                        f"seeded savings autosave transfer id {A.T28_TRANSFER_ID} missing")
            else:
                j.check("was_scheduled", row_b.get("status") == "scheduled", row_b.get("status"))
                j.check("now_canceled", row_a.get("status") == "canceled", row_a.get("status"))
            ok = preserved(b, a, changes={"transfers": {A.T28_TRANSFER_ID: {"status"}}})
            j.check("other_state_preserved", ok,
                    "only that one status cell changed (the card transfer must stay scheduled)")
        j.check("answer_canceled", affirms(fa, "cancel"), fa)
        j.check("answer_amount", affirm_money(fa, A.T28_AMOUNT), fa)
        j.check("answer_date", contains_date_forms(fa, A.T28_DATE), fa)

    elif number == 29:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            j.check("visited_card_detail", navigated_path(t, f"/credit-cards/card/{A.T29_CARD_SLUG}"),
                    "DoorDash Rewards Mastercard detail page")
            j.check("visited_apply", navigated_prefix(t, f"/credit-cards/card/{A.T29_CARD_SLUG}/apply"),
                    "application form")
            apps = new_rows(b, a, "applications")
            j.check("exactly_one_application", len(apps) == 1,
                    f"new applications: {[r.get('id') for r in apps]}")
            if len(apps) == 1:
                row = apps[0]
                j.check("application_card", row.get("card_slug") == A.T29_CARD_SLUG,
                        f"card_slug: {row.get('card_slug')!r}")
                j.check("application_name", (row.get("applicant_name") or "").strip() == A.T29_APPLICANT,
                        f"applicant_name: {row.get('applicant_name')!r}")
                j.check("application_status", row.get("status") == "Received", row.get("status"))
                j.check("application_ref", row.get("ref_number") == A.T29_REF,
                        f"ref_number: {row.get('ref_number')!r}")
            ok = preserved(b, a, additions={"applications": [r["id"] for r in apps]})
            j.check("other_state_preserved", ok, "all unrelated rows/tables unchanged")
        j.check("answer_ref", A.T29_REF in (fa or ""), fa)
        j.check("answer_card_named", affirms_any(fa, list(A.T29_CARD_TOKENS)), fa)

    else:
        j.check("unknown_task", False, f"no grading rule for task {number}")

    j.emit()
